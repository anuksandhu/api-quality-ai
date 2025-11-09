"""
AI Analyzer - Uses LLMs to analyze API specs and generate test strategies
"""

import json
import logging
from typing import Dict, List, Any
from anthropic import Anthropic
import os

logger = logging.getLogger(__name__)


class AIAnalyzer:
    """AI-powered API analysis and test strategy generation"""
    
    def __init__(self, config: Dict):
        """Initialize AI analyzer with configuration"""
        self.config = config
        
        # Validate required fields
        required_fields = ['provider', 'model', 'api_key_env', 'temperature', 'max_tokens']
        missing = [f for f in required_fields if f not in config]
        if missing:
            raise ValueError(f"Missing required AI config fields: {', '.join(missing)}")
        
        self.provider = config['provider']
        
        # Get tests per endpoint from config
        test_gen_config = config.get('test_generation', {})
        self.tests_per_endpoint = test_gen_config.get('tests_per_endpoint', 4)
        
        # Initialize AI client
        if self.provider == 'anthropic':
            api_key = os.getenv(config['api_key_env'])
            if not api_key:
                raise ValueError(f"API key not found in environment variable: {config['api_key_env']}")
            self.client = Anthropic(
                api_key=api_key,
                timeout=120.0
            )
        else:
            raise ValueError(f"Unsupported AI provider: {self.provider}")
    
    def analyze_spec(self, spec_data: Dict) -> Dict[str, Any]:
        """
        Analyze OpenAPI spec and generate comprehensive test strategy
        
        Args:
            spec_data: Parsed OpenAPI specification
            
        Returns:
            Dictionary containing test scenarios and strategy
        """
        logger.info("Starting AI analysis of API specification...")
        
        # Build analysis prompt
        prompt = self._build_analysis_prompt(spec_data)
        
        # Get AI response
        response = self._call_ai(prompt)
        
        # Parse response into structured format
        analysis = self._parse_analysis_response(response, spec_data)
        
        logger.info(f"AI analysis complete: {len(analysis['test_scenarios'])} scenarios identified")
        
        return analysis
    
    def _build_analysis_prompt(self, spec_data: Dict) -> str:
        """Build the prompt for AI analysis"""
        
        # Create a simplified version of spec for the prompt
        api_summary = {
            'title': spec_data['info']['title'],
            'version': spec_data['info']['version'],
            'description': spec_data['info']['description'],
            'base_url': spec_data['servers'][0]['url'] if spec_data['servers'] else 'unknown',
            'endpoints': []
        }
        
        # Simplify endpoints for prompt
        for endpoint in spec_data['endpoints']:
            api_summary['endpoints'].append({
                'path': endpoint['path'],
                'method': endpoint['method'],
                'summary': endpoint['summary'],
                'parameters': [
                    {
                        'name': p['name'],
                        'in': p['in'],
                        'required': p['required'],
                        'type': p['schema'].get('type', 'string')
                    }
                    for p in endpoint['parameters']
                ],
                'request_body': endpoint['request_body'] is not None,
                'responses': list(endpoint['responses'].keys())
            })
        
        # Calculate total tests based on config
        num_endpoints = len(api_summary['endpoints'])
        total_tests = num_endpoints * self.tests_per_endpoint
        
        # Build prompt with tests_per_endpoint from config
        prompt = f"""You are an expert QA engineer analyzing an API specification to create a comprehensive test strategy.

API Specification Summary:
{json.dumps(api_summary, indent=2)}

Generate test scenarios for this API. For EACH of the {num_endpoints} endpoints, create EXACTLY {self.tests_per_endpoint} test scenarios:
1. One positive test (valid request, expected 200/201)
2. One negative test (invalid input, expected 400/422)
3. One edge case (boundary values, null, empty strings)
4. One security test (authentication, authorization, or injection prevention)

This means you should generate {total_tests} total test scenarios.

CRITICAL: Return ONLY valid JSON. Do NOT use JavaScript code like .repeat() or template literals.
Use actual values in test_data, not code expressions.

CORRECT example:
{{"test_data": {{"parameters": {{}}, "body": {{"title": "Test Post", "body": "Test content", "userId": 1}}}}}}

WRONG example (DO NOT DO THIS):
{{"test_data": {{"body": {{"title": "A".repeat(1000)}}}}}}

Return JSON with this EXACT structure:
{{
  "overall_strategy": "Brief test strategy overview",
  "test_scenarios": [
    {{
      "endpoint": "POST /posts",
      "test_type": "positive",
      "scenario_name": "Test creating valid post",
      "description": "Validates successful post creation",
      "priority": "high",
      "test_data": {{
        "parameters": {{}},
        "body": {{"title": "Sample Post", "body": "Sample content", "userId": 1}}
      }},
      "expected_status": 201,
      "assertions": ["Check response schema", "Verify post ID returned"]
    }}
  ],
  "risk_areas": ["Authentication bypass", "Input validation"],
  "coverage_gaps": ["Performance testing"]
}}

For JSONPlaceholder API specifically:
- Use user IDs 1-10 (these exist)
- Use post IDs 1-100 (these exist)
- Positive tests should use ID 1 or 2

Rules:
1. Return ONLY the JSON object - no text before or after
2. Use actual string/number values, not JavaScript expressions
3. Ensure all JSON arrays have proper comma separators
4. Test types: "positive", "negative", "edge_case", or "security"
5. Generate all {total_tests} scenarios"""

        return prompt

    def _call_ai(self, prompt: str) -> str:
        """Call AI API and get response"""
        
        logger.debug("Calling AI API...")
        
        try:
            if self.provider == 'anthropic':
                # NO DEFAULTS - all values must be in config
                response = self.client.messages.create(
                    model=self.config['model'],
                    max_tokens=self.config['max_tokens'],
                    temperature=self.config['temperature'],
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                
                return response.content[0].text
            
        except Exception as e:
            logger.error(f"AI API call failed: {e}")
            raise
    
    def _parse_analysis_response(self, response: str, spec_data: Dict) -> Dict:
        """Parse AI response into structured format"""
        
        try:
            # Extract JSON from response (AI might include explanation)
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in AI response")
            
            json_str = response[json_start:json_end]
            
            # Try to fix common JSON issues
            json_str = self._fix_json_format(json_str)
            
            analysis = json.loads(json_str)
            
            # Validate structure
            if 'test_scenarios' not in analysis:
                raise ValueError("AI response missing 'test_scenarios'")
            
            # Enrich with spec data
            analysis['api_info'] = spec_data['info']
            analysis['total_endpoints'] = len(spec_data['endpoints'])
            analysis['total_scenarios'] = len(analysis['test_scenarios'])
            
            # Calculate coverage
            covered_endpoints = set()
            for scenario in analysis['test_scenarios']:
                covered_endpoints.add(scenario['endpoint'])
            
            analysis['coverage_percentage'] = (
                len(covered_endpoints) / len(spec_data['endpoints']) * 100
                if spec_data['endpoints'] else 0
            )
            
            return analysis
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"Problematic JSON around error: {json_str[max(0, e.pos-100):e.pos+100]}")
            
            # Try to salvage partial response
            logger.warning("Attempting to salvage partial AI response...")
            return self._create_fallback_analysis(spec_data)
            
        except Exception as e:
            logger.error(f"Error parsing AI analysis: {e}")
            logger.warning("Falling back to minimal test scenarios")
            return self._create_fallback_analysis(spec_data)
    
    def _fix_json_format(self, json_str: str) -> str:
        """Attempt to fix common JSON formatting issues"""
        import re
        
        # Fix missing commas between array elements
        json_str = re.sub(r'"\s*\n\s*([}\]])', r'"\n\1', json_str)
        
        # Fix missing commas between object properties
        json_str = re.sub(r'"\s*\n\s*"', r'",\n"', json_str)
        
        return json_str

    def _create_fallback_analysis(self, spec_data: Dict) -> Dict:
        """Create basic analysis when AI response fails"""
        logger.warning("Using fallback analysis with minimal test scenarios")
        
        # Create tests per endpoint based on config
        test_scenarios = []
        for endpoint in spec_data['endpoints']:
            # Determine expected status based on method
            if endpoint['method'] == 'POST':
                expected_status = 201
            elif endpoint['method'] == 'DELETE':
                expected_status = 204
            else:
                expected_status = 200
            
            # Create test data with realistic values
            test_data = {'parameters': {}, 'body': {}}
            
            # Add valid path parameters if endpoint has them
            if '{id}' in endpoint['path']:
                test_data['parameters']['id'] = 1
            elif '{userId}' in endpoint['path']:
                test_data['parameters']['userId'] = 1
            
            # Add body data for POST/PUT/PATCH requests
            if endpoint['method'] in ['POST', 'PUT', 'PATCH']:
                if 'post' in endpoint['path'].lower():
                    test_data['body'] = {
                        'title': 'Test Post',
                        'body': 'Test content',
                        'userId': 1
                    }
                elif 'user' in endpoint['path'].lower():
                    test_data['body'] = {
                        'name': 'Test User',
                        'username': 'testuser',
                        'email': 'test@example.com'
                    }
            
            test_scenarios.append({
                'endpoint': f"{endpoint['method']} {endpoint['path']}",
                'test_type': 'positive',
                'scenario_name': f"Test {endpoint['method']} {endpoint['path']}",
                'description': f"Basic test for {endpoint['summary']}",
                'priority': 'medium',
                'test_data': test_data,
                'expected_status': expected_status,
                'assertions': ['Check status code', 'Verify response']
            })
        
        return {
            'overall_strategy': 'Fallback strategy - minimal test coverage',
            'test_scenarios': test_scenarios,
            'risk_areas': ['AI analysis failed - manual review needed'],
            'coverage_gaps': ['Comprehensive test generation failed'],
            'api_info': spec_data['info'],
            'total_endpoints': len(spec_data['endpoints']),
            'total_scenarios': len(test_scenarios),
            'coverage_percentage': 100.0
        }

    def generate_test_name(self, scenario: Dict) -> str:
        """Generate a pytest-friendly test name"""
        endpoint = scenario['endpoint'].replace('/', '_').replace('{', '').replace('}', '')
        test_type = scenario['test_type']
        
        # Clean up scenario name
        name_parts = scenario['scenario_name'].lower().split()
        name = '_'.join(name_parts[:6])  # Limit length
        
        return f"test_{endpoint}_{test_type}_{name}"


def estimate_test_count(analysis: Dict) -> Dict[str, int]:
    """Estimate test counts by type"""
    counts = {
        'positive': 0,
        'negative': 0,
        'edge_case': 0,
        'security': 0
    }
    
    for scenario in analysis.get('test_scenarios', []):
        test_type = scenario.get('test_type', 'positive')
        counts[test_type] = counts.get(test_type, 0) + 1
    
    return counts
