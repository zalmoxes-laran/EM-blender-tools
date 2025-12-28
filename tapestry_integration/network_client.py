"""
Network client for Tapestry server communication

Handles:
- Connection testing
- Job submission
- Status monitoring
- Result retrieval
"""

import json


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
    Submit job to Tapestry server with file upload

    Uploads image files (RGB, depth, masks) along with job metadata.
    Files are sent as multipart/form-data instead of file paths.

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
        rgb_path = input_data.get('render_rgb')
        depth_path = input_data.get('render_depth')
        mask_paths = input_data.get('masks', {})

        # Prepare file handlers (keep them open during request)
        file_handles = []
        files = {}

        # Upload RGB image
        if rgb_path:
            try:
                f = open(rgb_path, 'rb')
                file_handles.append(f)
                files['render_rgb'] = ('render_rgb.png', f, 'image/png')
            except Exception as e:
                return False, f"Cannot read RGB file: {e}"

        # Upload depth image
        if depth_path:
            try:
                f = open(depth_path, 'rb')
                file_handles.append(f)
                files['render_depth'] = ('render_depth.png', f, 'image/png')
            except Exception as e:
                return False, f"Cannot read depth file: {e}"

        # Upload mask images (multiple files)
        for us_id, mask_path in mask_paths.items():
            try:
                f = open(mask_path, 'rb')
                file_handles.append(f)
                files[f'mask_{us_id}'] = (f'mask_{us_id}.png', f, 'image/png')
            except Exception as e:
                print(f"Warning: Cannot read mask for {us_id}: {e}")

        # Create job metadata (without file paths)
        job_metadata = {
            'job_id': job_data.get('job_id'),
            'proxies': job_data.get('proxies', {}),
            'generation_params': job_data.get('generation_params', {}),
            'metadata': job_data.get('metadata', {})
        }

        try:
            # Send multipart request with files + JSON metadata
            response = requests.post(
                url,
                files=files,
                data={'job_data': json.dumps(job_metadata)},
                timeout=30  # Longer timeout for file upload
            )
        finally:
            # Close all file handles
            for f in file_handles:
                f.close()

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
