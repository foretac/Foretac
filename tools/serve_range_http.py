#!/usr/bin/env python3
"""Serve static files with byte-range support for local video previews."""

from __future__ import annotations

import argparse
import os
import shutil
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class RangeRequestHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def send_head(self):  # noqa: N802 - standard-library hook name
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            if not self.path.endswith("/"):
                self.send_response(301)
                self.send_header("Location", self.path + "/")
                self.end_headers()
                return None
            return super().send_head()

        try:
            file_handle = open(path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return None

        size = os.fstat(file_handle.fileno()).st_size
        self.range_remaining = None
        range_header = self.headers.get("Range")
        if not range_header or not range_header.startswith("bytes="):
            self.send_response(200)
            self.send_header("Content-Length", str(size))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-type", self.guess_type(path))
            self.end_headers()
            return file_handle

        spec = range_header.removeprefix("bytes=").split(",", 1)[0].strip()
        try:
            start_text, end_text = spec.split("-", 1)
            if start_text:
                start = int(start_text)
                end = int(end_text) if end_text else size - 1
            else:
                length = int(end_text)
                start = max(0, size - length)
                end = size - 1
            if start < 0 or start >= size or end < start:
                raise ValueError
            end = min(end, size - 1)
        except ValueError:
            file_handle.close()
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None

        self.range_remaining = end - start + 1
        file_handle.seek(start)
        self.send_response(206)
        self.send_header("Content-Length", str(self.range_remaining))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-type", self.guess_type(path))
        self.end_headers()
        return file_handle

    def copyfile(self, source, outputfile):
        remaining = getattr(self, "range_remaining", None)
        if remaining is None:
            shutil.copyfileobj(source, outputfile)
            return
        while remaining > 0:
            chunk = source.read(min(64 * 1024, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", required=True)
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8125)
    args = parser.parse_args()
    handler = lambda *handler_args, **handler_kwargs: RangeRequestHandler(  # noqa: E731
        *handler_args, directory=args.directory, **handler_kwargs
    )
    server = ThreadingHTTPServer((args.bind, args.port), handler)
    print(f"Serving {args.directory} on http://{args.bind}:{args.port}/ with HTTP Range support", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
