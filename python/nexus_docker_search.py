#!/usr/bin/env python3
import urllib.request
import urllib.error
import urllib.parse
import base64
import re
import argparse
from typing import List, Dict, Any
import json

class NexusDockerSearch:
    def __init__(self, nexus_url: str, username: str, password: str, repository: str):
        """Initialize the Nexus Docker Search client.
        
        Args:
            nexus_url: Base URL of the Nexus server
            username: Nexus username
            password: Nexus password
            repository: Name of the Docker repository to search in
        """
        self.nexus_url = nexus_url.rstrip('/')
        self.username = username
        self.password = password
        self.repository = repository
        # Create basic auth header
        credentials = f"{username}:{password}".encode('utf-8')
        self.auth_header = f"Basic {base64.b64encode(credentials).decode('utf-8')}"

    def _make_request(self, url: str, params: Dict[str, str]) -> Dict[str, Any]:
        """Make an HTTP GET request with authentication.
        
        Args:
            url: The URL to request
            params: Query parameters
            
        Returns:
            Parsed JSON response
        """
        # Add query parameters to URL
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
            
        request = urllib.request.Request(url)
        request.add_header("Authorization", self.auth_header)
        
        try:
            with urllib.request.urlopen(request) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            raise Exception(f"HTTP Error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise Exception(f"URL Error: {e.reason}")

    def search_components(self, patterns: List[str]) -> List[Dict[str, Any]]:
        """Search for Docker components matching the given patterns.
        
        Args:
            patterns: List of regex patterns to match against image names
            
        Returns:
            List of matching components with their details
        """
        # Compile regex patterns
        compiled_patterns = [re.compile(pattern) for pattern in patterns]
        
        # Get all components from the repository
        url = f"{self.nexus_url}/service/rest/v1/components"
        params = {
            "repository": self.repository,
            "format": "docker"
        }
        
        matching_components = []
        continuation_token = None
        
        while True:
            if continuation_token:
                params["continuationToken"] = continuation_token
                
            data = self._make_request(url, params)
            
            # Check each component against the patterns
            for component in data.get("items", []):
                name = component.get("name", "")
                if any(pattern.search(name) for pattern in compiled_patterns):
                    matching_components.append({
                        "name": name,
                        "version": component.get("version", ""),
                        "sha256": component.get("assets", [{}])[0].get("checksum", {}).get("sha256", "")
                    })
            
            # Check if there are more results
            continuation_token = data.get("continuationToken")
            if not continuation_token:
                break
        
        return matching_components

def main():
    parser = argparse.ArgumentParser(description="Search for Docker images in Nexus using regex patterns")
    parser.add_argument("--url", default="http://localhost:8081", help="Nexus server URL")
    parser.add_argument("--username", default="admin", help="Nexus username")
    parser.add_argument("--password", default="admin", help="Nexus password")
    parser.add_argument("--repository", default="my-private-docker-repo", help="Docker repository name")
    parser.add_argument("patterns", nargs="+", help="Regex patterns to match against image names")
    parser.add_argument("--output", "-o", help="Output file for results (JSON format)")
    
    args = parser.parse_args()
    
    try:
        client = NexusDockerSearch(args.url, args.username, args.password, args.repository)
        results = client.search_components(args.patterns)
        
        # Print results
        print(f"\nFound {len(results)} matching images:")
        for result in results:
            print(f"\nImage: {result['name']}")
            print(f"Version: {result['version']}")
            print(f"SHA256: {result['sha256']}")
        
        # Save to file if specified
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\nResults saved to {args.output}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 