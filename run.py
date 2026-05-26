#!/usr/bin/env python3
"""
FreeCash Dynamic Port Orchestrator
Automatically detects host port conflicts and re-routes postgres, backend, and frontend
services to available ports, providing a seamless zero-configuration dev experience.
"""

import os
import sys
import socket
import subprocess

# ANSI Color Codes for Premium Console Styling
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
RED = "\033[31m"
RESET = "\033[0m"

def is_port_free(port: int) -> bool:
    """Checks if a host port is free by trying to bind to it on 127.0.0.1."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        try:
            s.bind(('127.0.0.1', port))
            return True
        except socket.error:
            return False

def find_next_free_port(start_port: int, service_name: str) -> tuple[int, bool]:
    """Finds the next free port starting from start_port. Returns (port, has_conflict)."""
    port = start_port
    has_conflict = False
    
    if not is_port_free(port):
        has_conflict = True
        while not is_port_free(port):
            port += 1
            
    return port, has_conflict

def main():
    # Print Welcome Banner
    print(f"\n{CYAN}{BOLD}======================================================================{RESET}")
    print(f"{CYAN}{BOLD}   💸  FreeCash Dynamic Port Orchestrator{RESET}")
    print(f"{CYAN}{BOLD}======================================================================{RESET}\n")
    
    print(f"🕵️  {BOLD}Scanning local ports for conflicts...{RESET}")
    
    # 1. Detect Available Ports
    pg_port, pg_conflict = find_next_free_port(5432, "PostgreSQL")
    backend_port, backend_conflict = find_next_free_port(8000, "Django Backend")
    front_port, front_conflict = find_next_free_port(5173, "React Frontend")
    
    # Print Port Mapping Status
    def format_status(default_port, actual_port, conflict):
        if conflict:
            return f"{YELLOW}{actual_port} [CONFLICT -> RESOLVED]{RESET}"
        return f"{GREEN}{actual_port} [FREE]{RESET}"
        
    print(f"   • {BOLD}PostgreSQL Database{RESET} : {default_port_format(5432)} -> Mapped to {format_status(5432, pg_port, pg_conflict)}")
    print(f"   • {BOLD}Django Backend API{RESET}  : {default_port_format(8000)} -> Mapped to {format_status(8000, backend_port, backend_conflict)}")
    print(f"   • {BOLD}React Vite Frontend{RESET} : {default_port_format(5173)} -> Mapped to {format_status(5173, front_port, front_conflict)}")
    
    # 2. Parse Existing .env File
    env_vars = {}
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    parts = line.split('=', 1)
                    if len(parts) == 2:
                        env_vars[parts[0].strip()] = parts[1].strip()
                        
    # Inject Detected Ports and Configuration
    env_vars['POSTGRES_PORT'] = str(pg_port)
    env_vars['BACKEND_PORT'] = str(backend_port)
    env_vars['FRONTEND_PORT'] = str(front_port)
    env_vars['VITE_API_URL'] = f"http://localhost:{backend_port}"
    
    # Write Dynamic env file
    env_docker_path = '.env.docker'
    with open(env_docker_path, 'w') as f:
        f.write("# ======================================================================\n")
        f.write("# Generated automatically by run.py - DO NOT EDIT MANUALLY\n")
        f.write("# ======================================================================\n\n")
        for key, val in env_vars.items():
            f.write(f"{key}={val}\n")
            
    # Print Dynamic Credentials / URLs
    print(f"\n{CYAN}{BOLD}   [Access URLs & Integration info]{RESET}")
    print(f"   ➜  {BOLD}Frontend Client:{RESET}    {BLUE}http://localhost:{front_port}{RESET}")
    print(f"   ➜  {BOLD}Backend API url:{RESET}    {BLUE}http://localhost:{backend_port}/api/{RESET}")
    print(f"   ➜  {BOLD}CORS Integration:{RESET}   Django allows origin {YELLOW}http://localhost:{front_port}{RESET}")
    print(f"   ➜  {BOLD}PostgreSQL Port:{RESET}    {BLUE}{pg_port}{RESET} (internal: 5432)")
    
    # 3. Launch Docker Compose
    print(f"\n{CYAN}{BOLD}======================================================================{RESET}")
    print(f"   🚀  {BOLD}Starting Docker Compose...{RESET} (Press {RED}{BOLD}Ctrl+C{RESET} to shut down)")
    print(f"{CYAN}{BOLD}======================================================================{RESET}\n")
    
    cmd = ['docker', 'compose', '--env-file', env_docker_path, 'up']
    
    # Forward any command-line arguments to docker compose
    if len(sys.argv) > 1:
        # Check if user wants down command or other options
        cmd.extend(sys.argv[1:])
        
    try:
        # Run Docker Compose
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}🛑  Ctrl+C detected. Shutting down containers gracefully...{RESET}")
        subprocess.run(['docker', 'compose', '--env-file', env_docker_path, 'down'])
        print(f"{GREEN}✓ Containers stopped successfully. Have a nice day!{RESET}\n")

def default_port_format(port):
    return f"{BOLD}{port}{RESET}"

if __name__ == '__main__':
    # Make sure we are in the workspace directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    main()
