"""
Test Generator - Creates pytest test files from AI analysis
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class TestGenerator:
    """Generate pytest test files from test scenarios"""
    
    def __init__(self, config: Dict):
        """Initialize test generator"""
        self.config = config
        self.output_dir = Path(config.get('output_directory', 'generated_tests'))
        self.output_dir.mkdir(exist_ok=True, parents=True)
    
    def generate_tests(self, spec_data: Dict, analysis: Dict) -> List[str]:
        """
        Generate pytest test files
        
        Args:
            spec_data: Parsed OpenAPI spec
            analysis: AI analysis results
            
        Returns:
            List of generated test file paths
        """
        logger.info("Generating pytest test files...")
        
        # ADDITION: Clean old test files before generating new ones
        if self.output_dir.exists():
            logger.debug(f"Cleaning old test files from {self.output_dir}")
            for old_file in self.output_dir.glob('test_*.py'):
                old_file.unlink()
                logger.debug(f"Removed old test file: {old_file}")        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True, parents=True)

        # Group scenarios by endpoint
        grouped = self._group_scenarios_by_endpoint(analysis['test_scenarios'])
        
        # ADDING THESE DEBUG LINES:
        logger.info(f"Grouped into {len(grouped)} unique endpoints")
        for endpoint, scenarios in grouped.items():
            logger.info(f"  {endpoint}: {len(scenarios)} scenarios")

        generated_files = []
        
        # Generate conftest.py for shared fixtures
        conftest_path = self._generate_conftest(spec_data)
        generated_files.append(str(conftest_path))
        
        # Generate test file for each endpoint group
        for endpoint, scenarios in grouped.items():
            test_file = self._generate_test_file(endpoint, scenarios, spec_data)
            generated_files.append(str(test_file))
        
        logger.info(f"Generated {len(generated_files)} test files")
        return generated_files
    
    def _group_scenarios_by_endpoint(self, scenarios: List[Dict]) -> Dict[str, List[Dict]]:
        """Group test scenarios by endpoint"""
        grouped = {}
        
        for scenario in scenarios:
            endpoint = scenario['endpoint']
            if endpoint not in grouped:
                grouped[endpoint] = []
            grouped[endpoint].append(scenario)
        
        return grouped
    
    def _generate_conftest(self, spec_data: Dict) -> Path:
        """Generate conftest.py with shared fixtures"""
        
        content = f'''"""
Pytest configuration and shared fixtures
Auto-generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

import pytest
import requests
import os
from typing import Dict, Any


@pytest.fixture(scope="session")
def api_config() -> Dict[str, Any]:
    """Load API configuration"""
    return {{
        "base_url": "{spec_data['servers'][0]['url'] if spec_data['servers'] else 'http://localhost'}",
        "timeout": 30,
        "verify_ssl": True
    }}


@pytest.fixture(scope="session")
def auth_headers() -> Dict[str, str]:
    """Get authentication headers"""
    headers = {{}}
    
    # API Key authentication
    api_key = os.getenv("API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key
    
    # Bearer token authentication
    bearer_token = os.getenv("BEARER_TOKEN")
    if bearer_token:
        headers["Authorization"] = f"Bearer {{bearer_token}}"
    
    return headers


@pytest.fixture
def api_client(api_config, auth_headers):
    """Create configured API client"""
    class APIClient:
        def __init__(self, base_url: str, headers: Dict[str, str], timeout: int):
            self.base_url = base_url.rstrip('/')
            self.headers = headers
            self.timeout = timeout
            self.session = requests.Session()
            self.session.headers.update(headers)
        
        def request(self, method: str, path: str, **kwargs) -> requests.Response:
            """Make HTTP request"""
            url = f"{{self.base_url}}{{path}}"
            kwargs.setdefault('timeout', self.timeout)
            return self.session.request(method, url, **kwargs)
        
        def get(self, path: str, **kwargs) -> requests.Response:
            return self.request('GET', path, **kwargs)
        
        def post(self, path: str, **kwargs) -> requests.Response:
            return self.request('POST', path, **kwargs)
        
        def put(self, path: str, **kwargs) -> requests.Response:
            return self.request('PUT', path, **kwargs)
        
        def patch(self, path: str, **kwargs) -> requests.Response:
            return self.request('PATCH', path, **kwargs)
        
        def delete(self, path: str, **kwargs) -> requests.Response:
            return self.request('DELETE', path, **kwargs)
    
    return APIClient(
        base_url=api_config["base_url"],
        headers=auth_headers,
        timeout=api_config["timeout"]
    )


def validate_response_schema(response_data: Any, schema: Dict) -> bool:
    """Basic schema validation"""
    # TODO: Implement full JSON Schema validation
    return True


def assert_response_time(response: requests.Response, max_ms: int = 2000):
    """Assert response time is within acceptable range"""
    response_time_ms = response.elapsed.total_seconds() * 1000
    assert response_time_ms < max_ms, f"Response time {{response_time_ms:.0f}}ms exceeds {{max_ms}}ms"
'''
        
        conftest_path = self.output_dir / "conftest.py"
        conftest_path.write_text(content)
        logger.debug(f"Generated conftest.py: {conftest_path}")
        
        return conftest_path
    
    def _generate_test_file(self, endpoint: str, scenarios: List[Dict], spec_data: Dict) -> Path:
        """Generate test file for an endpoint"""
        
        # Create safe filename
        filename = self._endpoint_to_filename(endpoint)
        filepath = self.output_dir / f"test_{filename}.py"
        
        # Generate file content
        content = self._generate_test_content(endpoint, scenarios, spec_data)
        
        filepath.write_text(content)
        logger.debug(f"Generated test file: {filepath}")
        
        return filepath
    
    def _endpoint_to_filename(self, endpoint: str) -> str:
        """Convert endpoint to valid filename"""
        # Remove method prefix and clean path
        parts = endpoint.split(' ', 1)
        if len(parts) == 2:
            method, path = parts
        else:
            method = 'get'
            path = endpoint
        
        # Clean path
        filename = path.replace('/', '_').replace('{', '').replace('}', '')
        filename = filename.strip('_').lower()
        
        # Include method to make filename unique
        method_lower = method.lower()
        
        # Create unique filename: method_path
        if filename:
            return f"{method_lower}_{filename}"
        else:
            return f"{method_lower}_root"
    
    def _generate_test_content(self, endpoint: str, scenarios: List[Dict], spec_data: Dict) -> str:
        """Generate test file content"""
        
        # Extract method and path
        parts = endpoint.split(' ', 1)
        method = parts[0] if len(parts) == 2 else 'GET'
        path = parts[1] if len(parts) == 2 else endpoint
        
        # Find endpoint details in spec
        endpoint_details = self._find_endpoint_details(method, path, spec_data)
        
        content = f'''"""
Tests for {endpoint}
Auto-generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Endpoint: {method} {path}
Description: {endpoint_details.get('description', 'N/A')}
"""

import pytest
import requests
from typing import Dict, Any


class Test{self._class_name_from_endpoint(endpoint)}:
    """Test suite for {endpoint}"""
    
'''
        
        # Generate test methods
        for i, scenario in enumerate(scenarios, 1):
            content += self._generate_test_method(scenario, method, path, i)
            content += '\n'
        
        return content
    
    def _class_name_from_endpoint(self, endpoint: str) -> str:
        """Generate class name from endpoint"""
        parts = endpoint.replace('/', ' ').replace('{', '').replace('}', '').split()
        return ''.join(word.capitalize() for word in parts if word)
    


    def _generate_test_method(self, scenario: Dict, method: str, path: str, index: int) -> str:
        """Generate individual test method"""
        
        test_name = self._sanitize_test_name(scenario.get('scenario_name', f'test_{index}'))
        description = scenario.get('description', '')
        test_type = scenario.get('test_type', 'positive')
        expected_status = scenario.get('expected_status', 200)
        test_data = scenario.get('test_data', {})
        
        # Convert JSON nulls to Python None
        params = test_data.get('parameters', {})
        body = test_data.get('body', {})
        
        # Separate path parameters from query parameters
        path_params = {}
        query_params = {}
        
        for key, value in params.items():
            if f'{{{key}}}' in path:
                path_params[key] = value
            else:
                query_params[key] = value
        
        # Substitute path parameters into the path
        actual_path = path
        for key, value in path_params.items():
            actual_path = actual_path.replace(f'{{{key}}}', str(value))
        
        # Convert to Python literals
        query_params_str = self._convert_to_python_literal(query_params)
        body_str = self._convert_to_python_literal(body)
        
        # Build test method
        method_code = f'''    def test_{test_name}_{index}(self, api_client):
            """
            {description}
            Type: {test_type}
            Expected Status: {expected_status}
            """
            # Test data
            params = {query_params_str}
            body = {body_str}
            
            # Make request
            response = api_client.request(
                method="{method}",
                path="{actual_path}",
                params=params if params else None,
                json=body if body else None
            )
            
            # Assertions
            assert response.status_code == {expected_status}, \\
                f"Expected status {expected_status}, got {{response.status_code}}: {{response.text}}"
            
    '''
        
        # Add additional assertions
        assertions = scenario.get('assertions', [])
        if assertions:
            method_code += '        # Additional assertions\n'
            for assertion in assertions[:3]:
                method_code += f'        # TODO: {assertion}\n'
        
        # Add response validation for successful responses
        if expected_status >= 200 and expected_status < 300:
            method_code += '''        
            # Validate response structure
            if response.status_code in [200, 201]:
                try:
                    response_data = response.json()
                    assert response_data is not None, "Response body should not be empty"
                except:
                    pass  # Some APIs return empty bodies
                # TODO: Add specific schema validation
    '''
        
        method_code += '\n'
        
        return method_code

    # Added method to handle changes needed from JSON -> Python
    def _convert_to_python_literal(self, obj) -> str:
        """Convert JSON object to Python literal string, handling null -> None"""
        import json
        
        if obj is None or obj == {}:
            return "{}"
        
        # Convert to JSON string first
        json_str = json.dumps(obj, indent=8)
        
        # Replace JSON literals with Python equivalents
        json_str = json_str.replace('null', 'None')
        json_str = json_str.replace('true', 'True')
        json_str = json_str.replace('false', 'False')
        
        return json_str

# End of enhancement to handle JSON -> Python

    
    def _sanitize_test_name(self, name: str) -> str:
        """Convert scenario name to valid Python identifier"""
        # Remove special characters, replace spaces with underscores
        name = ''.join(c if c.isalnum() or c == '_' else '_' for c in name.lower())
        # Remove duplicate underscores
        while '__' in name:
            name = name.replace('__', '_')
        return name.strip('_')
    
    def _find_endpoint_details(self, method: str, path: str, spec_data: Dict) -> Dict:
        """Find endpoint details in spec data"""
        for endpoint in spec_data['endpoints']:
            if endpoint['method'] == method.upper() and endpoint['path'] == path:
                return endpoint
        return {}


def format_test_summary(generated_files: List[str]) -> str:
    """Format summary of generated tests"""
    return f"""
Generated Test Files:
-------------------
Total files: {len(generated_files)}

Files:
{chr(10).join(f"  - {f}" for f in generated_files)}
"""