package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"reflect"
	"testing"
)

func TestNexusDockerSearch(t *testing.T) {
	// Mock server to simulate Nexus responses
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Verify request method
		if r.Method != http.MethodGet {
			t.Errorf("Expected GET request, got %s", r.Method)
		}

		// Check path and parameters
		if r.URL.Path != "/service/rest/v1/search" {
			t.Errorf("Expected /service/rest/v1/search path, got %s", r.URL.Path)
		}

		// Verify query parameters
		query := r.URL.Query()
		if query.Get("repository") != "test-repo" {
			t.Errorf("Expected repository=test-repo, got %s", query.Get("repository"))
		}
		if query.Get("format") != "docker" {
			t.Errorf("Expected format=docker, got %s", query.Get("format"))
		}

		// Return mock response based on the pattern
		switch query.Get("name") {
		case "test/*":
			json.NewEncoder(w).Encode(map[string]interface{}{
				"items": []map[string]interface{}{
					{
						"name":    "test/image1",
						"version": "latest",
						"assets": []map[string]interface{}{
							{
								"checksum": map[string]string{
									"sha256": "sha256-2",
								},
							},
						},
					},
					{
						"name":    "test/image1",
						"version": "1",
						"assets": []map[string]interface{}{
							{
								"checksum": map[string]string{
									"sha256": "sha256-1",
								},
							},
						},
					},
					{
						"name":    "test/image1",
						"version": "2",
						"assets": []map[string]interface{}{
							{
								"checksum": map[string]string{
									"sha256": "sha256-2",
								},
							},
						},
					},
				},
			})
		default:
			// Return empty items array
			json.NewEncoder(w).Encode(map[string]interface{}{
				"items": []map[string]interface{}{},
			})
		}
	}))
	defer server.Close()

	// Create client with test server URL
	client := NewNexusDockerSearch(server.URL, "test-repo", "", "", true, false)

	// Test cases
	tests := []struct {
		name     string
		patterns []string
		want     map[string][]string
		wantErr  bool
	}{
		{
			name:     "Basic search",
			patterns: []string{"test/*"},
			want: map[string][]string{
				"test/image1": {"latest", "2", "1"},
			},
			wantErr: false,
		},
		{
			name:     "No matches",
			patterns: []string{"nonexistent/*"},
			want:     map[string][]string{},
			wantErr:  false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := client.SearchImages(tt.patterns)
			if (err != nil) != tt.wantErr {
				t.Errorf("SearchImages() error = %v, wantErr %v", err, tt.wantErr)
				return
			}

			// Compare maps, handling nil/empty cases
			if len(got) == 0 && len(tt.want) == 0 {
				// Both are empty, test passes
			} else if !reflect.DeepEqual(got, tt.want) {
				t.Errorf("SearchImages() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestFilterTags(t *testing.T) {
	client := NewNexusDockerSearch("http://example.com", "test-repo", "", "", true, false)

	tests := []struct {
		name          string
		tags          []string
		latestDigest  string
		versionDigest string
		want          []string
	}{
		{
			name:          "Latest matches highest version",
			tags:          []string{"latest", "1", "2"},
			latestDigest:  "sha256-2",
			versionDigest: "sha256-2",
			want:          []string{"latest", "2", "1"},
		},
		{
			name:          "Latest doesn't match highest version",
			tags:          []string{"latest", "1", "2"},
			latestDigest:  "sha256-old",
			versionDigest: "sha256-new",
			want:          []string{"2", "1"},
		},
		{
			name:          "No latest tag",
			tags:          []string{"1", "2", "3"},
			latestDigest:  "",
			versionDigest: "sha256-1",
			want:          []string{"3", "2"},
		},
		{
			name:          "Empty tags",
			tags:          []string{},
			latestDigest:  "",
			versionDigest: "",
			want:          nil,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := client.filterTags(tt.tags, tt.latestDigest, tt.versionDigest)
			if !reflect.DeepEqual(got, tt.want) {
				t.Errorf("filterTags() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestProcessImages(t *testing.T) {
	client := NewNexusDockerSearch("http://example.com", "test-repo", "", "", true, false)

	tests := []struct {
		name   string
		images []map[string]string
		want   map[string][]string
	}{
		{
			name: "Multiple versions with latest",
			images: []map[string]string{
				{"name": "test/image1", "version": "latest", "sha256": "sha256-2"},
				{"name": "test/image1", "version": "1", "sha256": "sha256-1"},
				{"name": "test/image1", "version": "2", "sha256": "sha256-2"},
			},
			want: map[string][]string{
				"test/image1": {"latest", "2", "1"},
			},
		},
		{
			name: "Multiple images",
			images: []map[string]string{
				{"name": "test/image1", "version": "1", "sha256": "sha256-1"},
				{"name": "test/image2", "version": "2", "sha256": "sha256-2"},
			},
			want: map[string][]string{
				"test/image1": {"1"},
				"test/image2": {"2"},
			},
		},
		{
			name:   "Empty input",
			images: []map[string]string{},
			want:   map[string][]string{},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := client.processImages(tt.images)
			if err != nil {
				t.Errorf("processImages() error = %v", err)
				return
			}
			if !reflect.DeepEqual(got, tt.want) {
				t.Errorf("processImages() = %v, want %v", got, tt.want)
			}
		})
	}
}
