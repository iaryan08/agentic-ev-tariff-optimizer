import http.server
import socketserver
import os

PORT = 8000

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Override to prevent spamming logs in background tasks
        pass

if __name__ == "__main__":
    # Ensure working directory is the app folder
    app_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(app_dir)
    
    # Enable socket reuse to avoid "address already in use" errors on restart
    socketserver.TCPServer.allow_reuse_address = True
    
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"\n==========================================")
        print(f"EV Charging Dynamic Pricing Dashboard Server")
        print(f"Access URL: http://localhost:{PORT}")
        print(f"==========================================\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping server.")
            httpd.server_close()
