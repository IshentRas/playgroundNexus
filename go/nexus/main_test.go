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
			json.NewEncoder(w).Encode(NexusResponse{
				Items: []Component{
					{
						Name:    "test/image1",
						Version: "latest",
						Assets: []Asset{
							{Checksum: Checksum{SHA256: "sha256-2"}},
						},
					},
					{
						Name:    "test/image1",
						Version: "1",
						Assets: []Asset{
							{Checksum: Checksum{SHA256: "sha256-1"}},
						},
					},
					{
						Name:    "test/image1",
						Version: "2",
						Assets: []Asset{
							{Checksum: Checksum{SHA256: "sha256-2"}},
						},
					},
				},
			})
		default:
			// Return empty items array, not null
			json.NewEncoder(w).Encode(NexusResponse{
				Items: []Component{},
			})
		}
	}))
	defer server.Close()

	// Create client with test server URL
	client := NewNexusDockerSearch(server.URL, "test-repo", "", "", true, false)

	// Test cases
	tests := []struct {
		name         string
		patterns     []string
		wantRaw      []SearchResult
		wantFiltered ImageResult
		wantErr      bool
	}{
		{
			name:     "Basic search",
			patterns: []string{"test/*"},
			wantRaw: []SearchResult{
				{Name: "test/image1", Version: "latest", SHA256: "sha256-2"},
				{Name: "test/image1", Version: "1", SHA256: "sha256-1"},
				{Name: "test/image1", Version: "2", SHA256: "sha256-2"},
			},
			wantFiltered: ImageResult{
				"test/image1": []string{"latest", "2", "1"},
			},
			wantErr: false,
		},
		{
			name:         "No matches",
			patterns:     []string{"nonexistent/*"},
			wantRaw:      []SearchResult{},
			wantFiltered: ImageResult{},
			wantErr:      false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Test raw search
			gotRaw, err := client.SearchImages(tt.patterns)
			if (err != nil) != tt.wantErr {
				t.Errorf("SearchImages() error = %v, wantErr %v", err, tt.wantErr)
				return
			}

			// Compare slices, handling nil/empty cases
			if len(gotRaw) == 0 && len(tt.wantRaw) == 0 {
				// Both are empty, test passes
			} else if !reflect.DeepEqual(gotRaw, tt.wantRaw) {
				t.Errorf("SearchImages() = %v, want %v", gotRaw, tt.wantRaw)
			}

			// Test filtered search
			gotFiltered, err := client.SearchAndFilterImages(tt.patterns)
			if (err != nil) != tt.wantErr {
				t.Errorf("SearchAndFilterImages() error = %v, wantErr %v", err, tt.wantErr)
				return
			}

			// Compare maps, handling nil/empty cases
			if len(gotFiltered) == 0 && len(tt.wantFiltered) == 0 {
				// Both are empty, test passes
			} else if !reflect.DeepEqual(gotFiltered, tt.wantFiltered) {
				t.Errorf("SearchAndFilterImages() = %v, want %v", gotFiltered, tt.wantFiltered)
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
			want:          []string{},
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
		images []SearchResult
		want   ImageResult
	}{
		{
			name: "Multiple versions with latest",
			images: []SearchResult{
				{Name: "test/image1", Version: "latest", SHA256: "sha256-2"},
				{Name: "test/image1", Version: "1", SHA256: "sha256-1"},
				{Name: "test/image1", Version: "2", SHA256: "sha256-2"},
			},
			want: ImageResult{
				"test/image1": []string{"latest", "2", "1"},
			},
		},
		{
			name: "Multiple images",
			images: []SearchResult{
				{Name: "test/image1", Version: "1", SHA256: "sha256-1"},
				{Name: "test/image2", Version: "2", SHA256: "sha256-2"},
			},
			want: ImageResult{
				"test/image1": []string{"1"},
				"test/image2": []string{"2"},
			},
		},
		{
			name:   "Empty input",
			images: []SearchResult{},
			want:   ImageResult{},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := client.processImages(tt.images)
			if !reflect.DeepEqual(got, tt.want) {
				t.Errorf("processImages() = %v, want %v", got, tt.want)
			}
		})
	}
} 