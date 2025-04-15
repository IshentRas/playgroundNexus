#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest
from unittest.mock import patch, MagicMock
import json
import base64
import os
import sys
import urllib.error
import ssl
import urllib.parse

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from python.nexus_docker_search import NexusDockerSearch

class TestNexusDockerSearch(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.nexus_url = "http://nexus.example.com"
        self.repository = "docker-hosted"
        self.username = "admin"
        self.password = "password"
        self.verbose = True
        
        # Mock responses for single pattern search
        self.mock_single_pattern_response = {
            "items": [
                {
                    "name": "test/image1",
                    "version": "latest",
                    "assets": [
                        {
                            "checksum": {
                                "sha256": "abc123"
                            }
                        }
                    ]
                },
                {
                    "name": "test/image2",
                    "version": "v1.0",
                    "assets": [
                        {
                            "checksum": {
                                "sha256": "def456"
                            }
                        }
                    ]
                }
            ]
        }
        
        # Mock responses for multiple pattern search
        self.mock_multiple_pattern_response = {
            "items": [
                {
                    "name": "test/image1",
                    "version": "latest",
                    "assets": [
                        {
                            "checksum": {
                                "sha256": "abc123"
                            }
                        }
                    ]
                },
                {
                    "name": "test/image2",
                    "version": "v1.0",
                    "assets": [
                        {
                            "checksum": {
                                "sha256": "def456"
                            }
                        }
                    ]
                },
                {
                    "name": "other/image3",
                    "version": "latest",
                    "assets": [
                        {
                            "checksum": {
                                "sha256": "ghi789"
                            }
                        }
                    ]
                }
            ]
        }

    def test_init_without_auth(self):
        """Test initialization without authentication."""
        client = NexusDockerSearch(self.nexus_url, self.repository)
        self.assertEqual(client.nexus_url, f"{self.nexus_url}/service/rest/v1/search")
        self.assertIsNone(client.username)
        self.assertIsNone(client.password)
        self.assertIsNone(client.auth_header)

    def test_init_with_auth(self):
        """Test initialization with authentication."""
        client = NexusDockerSearch(self.nexus_url, self.repository, self.username, self.password)
        self.assertEqual(client.nexus_url, f"{self.nexus_url}/service/rest/v1/search")
        self.assertEqual(client.username, self.username)
        self.assertEqual(client.password, self.password)
        self.assertIsNotNone(client.auth_header)

    @patch('urllib.request.urlopen')
    def test_make_request_without_auth(self, mock_urlopen):
        """Test making a request without authentication."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"test": "data"}).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        client = NexusDockerSearch(self.nexus_url, self.repository)
        response = client._make_request("http://test.com")
        
        # Verify request was made without auth header
        mock_urlopen.assert_called_once()
        request = mock_urlopen.call_args[0][0]
        self.assertNotIn("Authorization", request.headers)
        self.assertEqual(response, {"test": "data"})

    @patch('urllib.request.urlopen')
    def test_make_request_with_auth(self, mock_urlopen):
        """Test making a request with authentication."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"test": "data"}).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        client = NexusDockerSearch(self.nexus_url, self.repository, self.username, self.password)
        response = client._make_request("http://test.com")
        
        # Verify request was made with auth header
        mock_urlopen.assert_called_once()
        request = mock_urlopen.call_args[0][0]
        self.assertIn("Authorization", request.headers)
        self.assertEqual(response, {"test": "data"})

    @patch('urllib.request.urlopen')
    def test_search_images_single_pattern(self, mock_urlopen):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(self.mock_single_pattern_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Initialize client
        client = NexusDockerSearch(
            self.nexus_url,
            self.repository,
            self.username,
            self.password,
            verbose=self.verbose
        )
        
        # Test single pattern search
        results = client.search_images(["test/image.*"])
        
        # Verify results
        self.assertEqual(len(results), 2)
        
        # Verify first image
        self.assertEqual(results[0]["name"], "test/image1")
        self.assertEqual(results[0]["version"], "latest")
        self.assertEqual(results[0]["sha256"], "abc123")
        
        # Verify second image
        self.assertEqual(results[1]["name"], "test/image2")
        self.assertEqual(results[1]["version"], "v1.0")
        self.assertEqual(results[1]["sha256"], "def456")
        
        # Verify URL was called with correct parameters
        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args[0][0]
        parsed_url = urllib.parse.urlparse(call_args.full_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        self.assertEqual(query_params["name"][0], "test/image.*")
        self.assertEqual(query_params["repository"][0], "docker-hosted")
        self.assertEqual(query_params["format"][0], "docker")

    @patch('urllib.request.urlopen')
    def test_search_images_multiple_patterns(self, mock_urlopen):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(self.mock_multiple_pattern_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Initialize client
        client = NexusDockerSearch(
            self.nexus_url,
            self.repository,
            self.username,
            self.password,
            verbose=self.verbose
        )
        
        # Test multiple pattern search
        results = client.search_images(["test/image1", "test/image2"])
        
        # Verify results
        self.assertEqual(len(results), 2)
        
        # Verify first image
        self.assertEqual(results[0]["name"], "test/image1")
        self.assertEqual(results[0]["version"], "latest")
        self.assertEqual(results[0]["sha256"], "abc123")
        
        # Verify second image
        self.assertEqual(results[1]["name"], "test/image2")
        self.assertEqual(results[1]["version"], "v1.0")
        self.assertEqual(results[1]["sha256"], "def456")
        
        # Verify URL was called with correct parameters
        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args[0][0]
        parsed_url = urllib.parse.urlparse(call_args.full_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        self.assertNotIn("name", query_params)  # No name parameter for multiple patterns
        self.assertEqual(query_params["repository"][0], "docker-hosted")
        self.assertEqual(query_params["format"][0], "docker")

    @patch('urllib.request.urlopen')
    def test_search_images_no_matches(self, mock_urlopen):
        # Setup mock response with no matches
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"items": []}).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Initialize client
        client = NexusDockerSearch(
            self.nexus_url,
            self.repository,
            self.username,
            self.password,
            verbose=self.verbose
        )
        
        # Test search with no matches
        results = client.search_images(["nonexistent/image"])
        
        # Verify no results
        self.assertEqual(len(results), 0)
        
        # Verify URL was called with correct parameters
        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args[0][0]
        parsed_url = urllib.parse.urlparse(call_args.full_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        self.assertEqual(query_params["name"][0], "nonexistent/image")
        self.assertEqual(query_params["repository"][0], "docker-hosted")
        self.assertEqual(query_params["format"][0], "docker")

    @patch('urllib.request.urlopen')
    def test_search_images_error_handling(self, mock_urlopen):
        # Setup mock to raise an exception
        mock_urlopen.side_effect = Exception("Test error")
        
        # Initialize client
        client = NexusDockerSearch(
            self.nexus_url,
            self.repository,
            self.username,
            self.password,
            verbose=self.verbose
        )
        
        # Test error handling
        results = client.search_images(["test/image"])
        
        # Verify empty results on error
        self.assertEqual(len(results), 0)

    @patch('urllib.request.urlopen')
    def test_http_error_handling(self, mock_urlopen):
        """Test handling of HTTP errors."""
        # Setup mock to raise HTTPError
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "http://test.com", 404, "Not Found", {}, None
        )
        
        client = NexusDockerSearch(self.nexus_url, self.repository)
        with self.assertRaises(Exception) as context:
            client._make_request("http://test.com")
        
        self.assertIn("HTTP Error 404", str(context.exception))

    @patch('urllib.request.urlopen')
    def test_url_error_handling(self, mock_urlopen):
        """Test handling of URL errors."""
        # Setup mock to raise URLError
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        
        client = NexusDockerSearch(self.nexus_url, self.repository)
        with self.assertRaises(Exception) as context:
            client._make_request("http://test.com")
        
        self.assertIn("URL Error", str(context.exception))

if __name__ == '__main__':
    unittest.main() 