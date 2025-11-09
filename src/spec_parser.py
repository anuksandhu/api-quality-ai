"""
OpenAPI Specification Parser
Handles parsing and validation of OpenAPI 3.0+ specifications
"""

import yaml
import json
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


class SpecParser:
    """Parse and extract information from OpenAPI specifications"""
    
    def __init__(self, spec_source: str):
        """
        Initialize the parser
        
        Args:
            spec_source: URL or file path to OpenAPI spec
        """
        self.spec_source = spec_source
        self.spec_data: Optional[Dict] = None
        
    def parse(self) -> Dict[str, Any]:
        """
        Parse the OpenAPI specification
        
        Returns:
            Dictionary containing structured spec data
        """
        # Load the spec
        raw_spec = self._load_spec()
        self.spec_data = raw_spec
        
        # Extract structured information
        parsed_data = {
            'info': self._extract_info(raw_spec),
            'servers': self._extract_servers(raw_spec),
            'endpoints': self._extract_endpoints(raw_spec),
            'schemas': self._extract_schemas(raw_spec),
            'security': self._extract_security(raw_spec),
            'raw_spec': raw_spec
        }
        
        logger.info(f"Parsed spec: {parsed_data['info']['title']} v{parsed_data['info']['version']}")
        logger.info(f"Found {len(parsed_data['endpoints'])} endpoints")
        
        return parsed_data
    
    def _load_spec(self) -> Dict:
        """Load spec from URL or file"""
        if self._is_url(self.spec_source):
            return self._load_from_url(self.spec_source)
        else:
            return self._load_from_file(self.spec_source)
    
    def _is_url(self, source: str) -> bool:
        """Check if source is a URL"""
        parsed = urlparse(source)
        return parsed.scheme in ('http', 'https')
    
    def _load_from_url(self, url: str) -> Dict:
        """Load spec from URL"""
        logger.debug(f"Fetching spec from URL: {url}")
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # Try JSON first, then YAML
            try:
                return response.json()
            except json.JSONDecodeError:
                return yaml.safe_load(response.text)
                
        except requests.RequestException as e:
            raise ValueError(f"Failed to fetch spec from URL: {e}")
    
    def _load_from_file(self, filepath: str) -> Dict:
        """Load spec from local file"""
        path = Path(filepath)
        
        if not path.exists():
            raise FileNotFoundError(f"Spec file not found: {filepath}")
        
        logger.debug(f"Loading spec from file: {filepath}")
        
        with open(path, 'r') as f:
            if path.suffix in ('.yaml', '.yml'):
                return yaml.safe_load(f)
            elif path.suffix == '.json':
                return json.load(f)
            else:
                # Try to detect format
                content = f.read()
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return yaml.safe_load(content)
    
    def _extract_info(self, spec: Dict) -> Dict:
        """Extract API info"""
        info = spec.get('info', {})
        return {
            'title': info.get('title', 'Unknown API'),
            'version': info.get('version', '1.0.0'),
            'description': info.get('description', ''),
            'contact': info.get('contact', {}),
            'license': info.get('license', {})
        }
    
    def _extract_servers(self, spec: Dict) -> List[Dict]:
        """Extract server information"""
        servers = spec.get('servers', [])
        if not servers:
            # Default server
            return [{'url': 'http://localhost', 'description': 'Default'}]
        
        return [
            {
                'url': server.get('url', ''),
                'description': server.get('description', ''),
                'variables': server.get('variables', {})
            }
            for server in servers
        ]
    
    def _extract_endpoints(self, spec: Dict) -> List[Dict]:
        """Extract all API endpoints"""
        paths = spec.get('paths', {})
        endpoints = []
        
        for path, path_item in paths.items():
            # Handle path-level parameters
            path_params = path_item.get('parameters', [])
            
            for method in ['get', 'post', 'put', 'patch', 'delete', 'options', 'head']:
                if method not in path_item:
                    continue
                
                operation = path_item[method]
                
                endpoint = {
                    'path': path,
                    'method': method.upper(),
                    'operation_id': operation.get('operationId', f"{method}_{path.replace('/', '_')}"),
                    'summary': operation.get('summary', ''),
                    'description': operation.get('description', ''),
                    'tags': operation.get('tags', []),
                    'parameters': self._merge_parameters(
                        path_params,
                        operation.get('parameters', [])
                    ),
                    'request_body': self._extract_request_body(operation.get('requestBody')),
                    'responses': self._extract_responses(operation.get('responses', {})),
                    'security': operation.get('security', spec.get('security', [])),
                    'deprecated': operation.get('deprecated', False)
                }
                
                endpoints.append(endpoint)
        
        return endpoints
    
    def _merge_parameters(self, path_params: List, op_params: List) -> List[Dict]:
        """Merge path-level and operation-level parameters"""
        all_params = []
        
        for param in path_params + op_params:
            if '$ref' in param:
                # TODO: Resolve $ref
                continue
            
            all_params.append({
                'name': param.get('name'),
                'in': param.get('in'),  # path, query, header, cookie
                'required': param.get('required', False),
                'schema': param.get('schema', {}),
                'description': param.get('description', ''),
                'example': param.get('example')
            })
        
        return all_params
    
    def _extract_request_body(self, request_body: Optional[Dict]) -> Optional[Dict]:
        """Extract request body schema"""
        if not request_body:
            return None
        
        content = request_body.get('content', {})
        
        # Support common content types
        for content_type in ['application/json', 'application/xml', 'multipart/form-data']:
            if content_type in content:
                return {
                    'content_type': content_type,
                    'schema': content[content_type].get('schema', {}),
                    'required': request_body.get('required', False),
                    'description': request_body.get('description', '')
                }
        
        return None
    
    def _extract_responses(self, responses: Dict) -> Dict[str, Dict]:
        """Extract response definitions"""
        extracted = {}
        
        for status_code, response in responses.items():
            content = response.get('content', {})
            
            # Get JSON response schema if available
            schema = None
            if 'application/json' in content:
                schema = content['application/json'].get('schema')
            
            extracted[status_code] = {
                'description': response.get('description', ''),
                'schema': schema,
                'headers': response.get('headers', {})
            }
        
        return extracted
    
    def _extract_schemas(self, spec: Dict) -> Dict:
        """Extract component schemas"""
        components = spec.get('components', {})
        return components.get('schemas', {})
    
    def _extract_security(self, spec: Dict) -> List[Dict]:
        """Extract security schemes"""
        components = spec.get('components', {})
        security_schemes = components.get('securitySchemes', {})
        
        return [
            {
                'name': name,
                'type': scheme.get('type'),
                'scheme': scheme.get('scheme'),
                'bearer_format': scheme.get('bearerFormat'),
                'in': scheme.get('in'),
                'name_param': scheme.get('name')
            }
            for name, scheme in security_schemes.items()
        ]


def get_endpoint_signature(endpoint: Dict) -> str:
    """Generate a unique signature for an endpoint"""
    return f"{endpoint['method']} {endpoint['path']}"


def find_endpoint_by_path(endpoints: List[Dict], method: str, path: str) -> Optional[Dict]:
    """Find an endpoint by method and path"""
    for endpoint in endpoints:
        if endpoint['method'] == method.upper() and endpoint['path'] == path:
            return endpoint
    return None