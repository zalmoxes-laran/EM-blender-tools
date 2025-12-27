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
    Submit job to Tapestry server

    Args:
        server_address: Server hostname/IP
        server_port: Server port
        job_data: Job JSON data

    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        import requests
    except ImportError:
        return False, "requests library not installed"

    url = f"http://{server_address}:{server_port}/jobs"

    try:
        response = requests.post(
            url,
            json=job_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            job_id = data.get('job_id', '?')
            status = data.get('status', '?')
            return True, f"Job {job_id} submitted ({status})"
        else:
            return False, f"HTTP {response.status_code}: {response.text}"

    except Exception as e:
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
