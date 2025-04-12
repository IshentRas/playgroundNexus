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

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from python.nexus_docker_search import NexusDockerSearch

class TestNexusDockerSearch(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.nexus_url = "http://test.nexus"
        self.username = "testuser"
        self.password = "testpass"
        self.repository = "test-repo"
        self.client = NexusDockerSearch(
            self.nexus_url,
            self.username,
            self.password,
            self.repository
        )

    def test_init(self):
        """Test initialization of NexusDockerSearch"""
        # Test URL handling
        client = NexusDockerSearch(
            "http://test.nexus/",  # with trailing slash
            self.username,
            self.password,
            self.repository
        )
        self.assertEqual(client.nexus_url, "http://test.nexus")
        
        # Test auth header generation
        expected_auth = f"Basic {base64.b64encode(b'testuser:testpass').decode('utf-8')}"
        self.assertEqual(self.client.auth_header, expected_auth)

        # Test SSL verification default
        self.assertTrue(self.client.verify_ssl)

        # Test SSL verification disabled
        client_no_ssl = NexusDockerSearch(
            self.nexus_url,
            self.username,
            self.password,
            self.repository,
            verify_ssl=False
        )
        self.assertFalse(client_no_ssl.verify_ssl)

    @patch('urllib.request.urlopen')
    def test_make_request(self, mock_urlopen):
        """Test _make_request method"""
        # Mock response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"test": "data"}).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Test request without params
        result = self.client._make_request("http://test.url", {})
        self.assertEqual(result, {"test": "data"})

        # Test request with params
        result = self.client._make_request("http://test.url", {"param": "value"})
        self.assertEqual(result, {"test": "data"})

        # Verify authorization header
        calls = mock_urlopen.call_args_list
        for call in calls:
            request = call[0][0]
            self.assertEqual(request.get_header("Authorization"), self.client.auth_header)

    @patch('urllib.request.urlopen')
    def test_make_request_https(self, mock_urlopen):
        """Test _make_request method with HTTPS"""
        # Mock response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"test": "data"}).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Test with SSL verification enabled
        client_ssl = NexusDockerSearch(
            "https://test.nexus",
            self.username,
            self.password,
            self.repository,
            verify_ssl=True
        )
        result = client_ssl._make_request("https://test.url", {})
        self.assertEqual(result, {"test": "data"})
        
        # Verify no SSL context was passed
        mock_urlopen.assert_called_with(ANY, context=None)

        # Test with SSL verification disabled
        client_no_ssl = NexusDockerSearch(
            "https://test.nexus",
            self.username,
            self.password,
            self.repository,
            verify_ssl=False
        )
        result = client_no_ssl._make_request("https://test.url", {})
        self.assertEqual(result, {"test": "data"})
        
        # Verify unverified SSL context was passed
        mock_urlopen.assert_called_with(ANY, context=ANY)
        context = mock_urlopen.call_args[1]['context']
        self.assertIsInstance(context, ssl.SSLContext)
        self.assertFalse(context.verify_mode)

    @patch('urllib.request.urlopen')
    def test_search_components(self, mock_urlopen):
        """Test search_components method"""
        # Mock paginated responses
        responses = [
            {
                "items": [
                    {"name": "test/image1", "version": "1.0", "assets": [{"checksum": {"sha256": "abc123"}}]},
                    {"name": "other/image", "version": "2.0", "assets": [{"checksum": {"sha256": "def456"}}]}
                ],
                "continuationToken": "token1"
            },
            {
                "items": [
                    {"name": "test/image2", "version": "3.0", "assets": [{"checksum": {"sha256": "ghi789"}}]}
                ],
                "continuationToken": None
            }
        ]

        def side_effect(*args, **kwargs):
            response = MagicMock()
            response.read.return_value = json.dumps(responses.pop(0)).encode('utf-8')
            return response

        mock_urlopen.return_value.__enter__.side_effect = side_effect

        # Test with pattern matching 'test/*'
        results = self.client.search_components(["test/.*"])
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["name"], "test/image1")
        self.assertEqual(results[0]["version"], "1.0")
        self.assertEqual(results[0]["sha256"], "abc123")
        self.assertEqual(results[1]["name"], "test/image2")

    @patch('urllib.request.urlopen')
    def test_error_handling(self, mock_urlopen):
        """Test error handling"""
        # Test HTTP error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "http://test.url", 404, "Not Found", None, None
        )
        with self.assertRaises(Exception) as context:
            self.client._make_request("http://test.url", {})
        self.assertTrue("HTTP Error 404" in str(context.exception))

        # Test URL error
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        with self.assertRaises(Exception) as context:
            self.client._make_request("http://test.url", {})
        self.assertTrue("URL Error" in str(context.exception))

if __name__ == '__main__':
    unittest.main() 