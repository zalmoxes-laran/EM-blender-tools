"""
Network client for Tapestry server communication

Handles:
- Connection testing
- Job submission
- Status monitoring
- Result retrieval
"""

import json
import io
import os
import time


def test_connection(server_address, server_port):
    """
    Test connection to Tapestry server

    Args:
        server_address: Server hostname/IP
        server_port: Server port

    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        import requests
    except ImportError:
        return False, "requests library not installed. Install with: pip install requests"

    url = f"http://{server_address}:{server_port}/api"

    try:
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            data = response.json()
            return True, f"{data.get('name', 'Tapestry')} v{data.get('version', '?')}"
        else:
            return False, f"HTTP {response.status_code}: {response.text}"

    except requests.exceptions.ConnectionError:
        return False, f"Cannot connect to {server_address}:{server_port}"
    except requests.exceptions.Timeout:
        return False, "Connection timeout"
    except Exception as e:
        return False, str(e)


def submit_job(server_address, server_port, job_data):
    """
    Submit job to Tapestry server with EXR + semantic JSON upload

    NEW PIPELINE (EXR-only):
    - Uploads EXR multilayer file (contains Combined, Depth, Normal, Cryptomatte)
    - Uploads semantic JSON (contains object names for Cryptomatte matching + RAG data)
    - Optional: RGB preview PNG for UI display

    Args:
        server_address: Server hostname/IP
        server_port: Server port
        job_data: Job JSON data (contains file paths to upload)

    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        import requests
    except ImportError:
        return False, "requests library not installed"

    url = f"http://{server_address}:{server_port}/jobs/upload"

    try:
        # Extract file paths from job_data
        input_data = job_data.get('input', {})
        exr_path = input_data.get('exr')  # NEW: EXR multilayer
        rgb_preview_path = input_data.get('rgb_preview')  # Optional preview
        semantic_json_path = input_data.get('semantic_json')  # NEW: Semantic data

        # Prepare files using BytesIO for proper binary handling
        files = {}

        # Upload EXR multilayer (REQUIRED)
        if exr_path:
            try:
                # Wait for file to be fully written by Blender
                max_wait = 10  # EXR can be larger, wait longer
                wait_time = 0
                while wait_time < max_wait:
                    if os.path.exists(exr_path):
                        # Check if file size is stable (file finished writing)
                        size1 = os.path.getsize(exr_path)
                        time.sleep(0.2)
                        size2 = os.path.getsize(exr_path)
                        if size1 == size2 and size1 > 0:
                            break
                    time.sleep(0.2)
                    wait_time += 0.2

                # Read EXR file
                with open(exr_path, 'rb') as f:
                    content = f.read()

                # Verify it's a valid EXR (starts with magic number)
                if not content.startswith(b'\x76\x2f\x31\x01'):
                    return False, f"EXR file is not valid (first bytes: {content[:4]})"

                print(f"EXR file verified: {len(content)} bytes, valid OpenEXR format")
                files['render_exr'] = ('render.exr', io.BytesIO(content), 'application/octet-stream')
            except Exception as e:
                return False, f"Cannot read EXR file: {e}"
        else:
            return False, "No EXR file provided"

        # Upload semantic JSON (REQUIRED)
        if semantic_json_path:
            try:
                with open(semantic_json_path, 'rb') as f:
                    content = f.read()
                files['semantic_json'] = ('semantic.json', io.BytesIO(content), 'application/json')
                print(f"Semantic JSON uploaded: {len(content)} bytes")
            except Exception as e:
                return False, f"Cannot read semantic JSON: {e}"
        else:
            return False, "No semantic JSON provided"

        # Upload RGB preview (OPTIONAL - for UI display)
        if rgb_preview_path and os.path.exists(rgb_preview_path):
            try:
                with open(rgb_preview_path, 'rb') as f:
                    content = f.read()
                files['rgb_preview'] = ('preview.png', io.BytesIO(content), 'image/png')
                print(f"RGB preview uploaded: {len(content)} bytes")
            except Exception as e:
                print(f"Warning: Could not upload RGB preview: {e}")

        # Create job metadata (without file paths)
        job_metadata = {
            'job_id': job_data.get('job_id'),
            'proxies': job_data.get('proxies', {}),
            'generation_params': job_data.get('generation_params', {}),
            'metadata': job_data.get('metadata', {})
        }

        # Send multipart request with files + JSON metadata
        response = requests.post(
            url,
            files=files,
            data={'job_data': json.dumps(job_metadata)},
            timeout=30  # Longer timeout for file upload
        )

        if response.status_code == 200:
            data = response.json()
            job_id = data.get('job_id', '?')
            status = data.get('status', '?')
            return True, f"Job {job_id} submitted ({status})"
        else:
            return False, f"HTTP {response.status_code}: {response.text}"

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, str(e)


def get_job_status(server_address, server_port, job_id):
    """
    Get status of submitted job

    Args:
        server_address: Server hostname/IP
        server_port: Server port
        job_id: Job identifier

    Returns:
        tuple: (success: bool, status_data: dict or error_message: str)
    """
    try:
        import requests
    except ImportError:
        return False, "requests library not installed"

    url = f"http://{server_address}:{server_port}/jobs/{job_id}"

    try:
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            return True, response.json()
        else:
            return False, f"HTTP {response.status_code}"

    except Exception as e:
        return False, str(e)


def download_result(server_address, server_port, job_id, output_path):
    """
    Download result from completed job

    Args:
        server_address: Server hostname/IP
        server_port: Server port
        job_id: Job identifier
        output_path: Local path to save result

    Returns:
        tuple: (success: bool, message: str)
    """
    # Check job status first
    success, status_data = get_job_status(server_address, server_port, job_id)

    if not success:
        return False, f"Cannot get job status: {status_data}"

    if status_data.get('status') != 'completed':
        return False, f"Job not completed (status: {status_data.get('status')})"

    # Get output path from status
    remote_output = status_data.get('output_path')

    if not remote_output:
        return False, "No output path in job data"

    # In future, implement actual file download
    # For now, just return the remote path
    return True, f"Result available at: {remote_output}"
