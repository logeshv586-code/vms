import subprocess
import sys
import os
import time
import signal
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Store process references
processes = []

def start_main_server():
    """Start the main FastAPI server on port 8000"""
    logger.info("Starting main server on port 8000...")
    process = subprocess.Popen([sys.executable, "main.py"],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              text=True)
    processes.append(process)
    logger.info(f"Main server started with PID {process.pid}")
    return process



def cleanup(signum=None, frame=None):
    """Clean up all processes on exit"""
    logger.info("Cleaning up processes...")
    for process in processes:
        try:
            logger.info(f"Terminating process with PID {process.pid}")
            process.terminate()
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning(f"Process {process.pid} did not terminate, killing it")
            process.kill()
        except Exception as e:
            logger.error(f"Error terminating process: {str(e)}")
    logger.info("All processes terminated")
    sys.exit(0)

def monitor_output(process, name):
    """Monitor and log the output of a process"""
    while True:
        output = process.stdout.readline()
        if output:
            logger.info(f"[{name}] {output.strip()}")
        error = process.stderr.readline()
        if error:
            logger.error(f"[{name}] {error.strip()}")

        # Check if process is still running
        if process.poll() is not None:
            logger.warning(f"{name} process exited with code {process.returncode}")
            remaining_output, remaining_error = process.communicate()
            if remaining_output:
                logger.info(f"[{name}] {remaining_output.strip()}")
            if remaining_error:
                logger.error(f"[{name}] {remaining_error.strip()}")
            break

if __name__ == "__main__":
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        # Start main server
        main_server = start_main_server()

        # Wait for server to start
        time.sleep(2)

        # Check if server started successfully
        if main_server.poll() is not None:
            logger.error(f"Main server failed to start (exit code {main_server.returncode})")
            cleanup()

        logger.info("Main server started successfully")

        # Keep the script running and monitor server output
        while True:
            # Check if server has exited
            if main_server.poll() is not None:
                logger.error(f"Main server exited unexpectedly with code {main_server.returncode}")
                cleanup()

            # Sleep to avoid high CPU usage
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        cleanup()
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        cleanup()
