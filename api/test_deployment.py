#!/usr/bin/env python3
"""
Deployment verification script.

This script can be run in CI/CD or manually to verify that all
API endpoints are working correctly after deployment.

Usage:
    python test_deployment.py [API_URL]

Example:
    python test_deployment.py http://localhost:8000
"""

import sys
from typing import Any, Dict

import requests


def test_endpoint(
    base_url: str, endpoint: str, expected_status: int = 200
) -> Dict[str, Any]:
    """Test a single endpoint and return results."""
    url = f"{base_url}{endpoint}"
    try:
        response = requests.get(url, timeout=10)
        return {
            "endpoint": endpoint,
            "url": url,
            "status": response.status_code,
            "expected": expected_status,
            "success": response.status_code == expected_status,
            "error": None,
        }
    except Exception as e:
        return {
            "endpoint": endpoint,
            "url": url,
            "status": None,
            "expected": expected_status,
            "success": False,
            "error": str(e),
        }


def main():
    """Run deployment verification tests."""
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

    print(f"🔍 Testing RSS Reader API deployment at: {base_url}")
    print("=" * 60)

    # Critical endpoints that MUST work
    critical_endpoints = [
        "/api/v1/health/liveness",
        "/api/v1/health/readiness",
        "/api/v1/feeds/",
        "/api/v1/categories/",  # This would have caught the missing categories bug!
    ]

    # Optional endpoints (may return different status codes)
    optional_endpoints = [
        ("/api/v1/export/opml", 200),
        ("/api/v1/sse/events", [200, 307]),  # SSE might redirect or work
    ]

    results = []
    failed_critical = []

    # Test critical endpoints
    print("🚨 Testing Critical Endpoints:")
    for endpoint in critical_endpoints:
        result = test_endpoint(base_url, endpoint)
        results.append(result)

        status_icon = "✅" if result["success"] else "❌"
        print(
            f"  {status_icon} {endpoint} -> {result['status']} {result.get('error', '')}"
        )

        if not result["success"]:
            failed_critical.append(result)

    print()

    # Test optional endpoints
    print("ℹ️  Testing Optional Endpoints:")
    for endpoint, expected in optional_endpoints:
        if isinstance(expected, list):
            # Multiple acceptable status codes
            result = test_endpoint(base_url, endpoint)
            result["success"] = result["status"] in expected
            result["expected"] = f"one of {expected}"
        else:
            result = test_endpoint(base_url, endpoint, expected)

        results.append(result)
        status_icon = "✅" if result["success"] else "⚠️"
        print(
            f"  {status_icon} {endpoint} -> {result['status']} {result.get('error', '')}"
        )

    print()

    # Test API discovery
    print("📋 Testing API Discovery:")
    discovery_result = test_endpoint(base_url, "/api/v1")
    if discovery_result["success"]:
        try:
            discovery_data = requests.get(f"{base_url}/api/v1").json()
            endpoints = discovery_data.get("endpoints", {})

            expected_in_discovery = [
                "categories",
                "feeds",
                "health",
                "sse",
                "import",
                "export",
            ]
            missing_from_discovery = [
                ep for ep in expected_in_discovery if ep not in endpoints
            ]

            if missing_from_discovery:
                print(f"  ⚠️  Missing from API discovery: {missing_from_discovery}")
            else:
                print("  ✅ All expected endpoints listed in API discovery")

        except Exception as e:
            print(f"  ❌ Failed to parse API discovery response: {e}")
    else:
        print(f"  ❌ API discovery endpoint failed: {discovery_result}")

    print()

    # Summary
    total_tests = len(results)
    passed_tests = len([r for r in results if r["success"]])

    print("📊 Summary:")
    print(f"  Total tests: {total_tests}")
    print(f"  Passed: {passed_tests}")
    print(f"  Failed: {total_tests - passed_tests}")

    if failed_critical:
        print()
        print("🚨 CRITICAL FAILURES:")
        for failure in failed_critical:
            error_msg = failure.get(
                "error", f"Status {failure['status']} != {failure['expected']}"
            )
            print(f"  - {failure['endpoint']}: {error_msg}")

        print()
        print("❌ DEPLOYMENT VERIFICATION FAILED")
        sys.exit(1)
    else:
        print()
        print("✅ DEPLOYMENT VERIFICATION PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
