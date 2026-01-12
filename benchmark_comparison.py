#!/usr/bin/env python3
"""
Benchmark script to compare cbor2 performance.

This script benchmarks:
1. loads() - direct bytes decoding
2. Streaming decode with CBORDecoder - tests read_size optimization
3. Various data patterns (small strings, large data, many small values)

Usage:
    # Benchmark current branch
    pip install -e .
    python benchmark_comparison.py --output current.json

    # Benchmark 5.7.1
    pip install cbor2==5.7.1
    python benchmark_comparison.py --output baseline.json

    # Compare results
    python benchmark_comparison.py --compare baseline.json current.json
"""

import argparse
import io
import json
import sys
import time
from contextlib import contextmanager

import cbor2


def get_version_info():
    """Get cbor2 version and whether C extension is available."""
    version = getattr(cbor2, "__version__", "unknown")
    try:
        import _cbor2
        has_c_ext = True
    except ImportError:
        has_c_ext = False
    return {"version": version, "c_extension": has_c_ext}


@contextmanager
def timer():
    """Context manager to time a block of code."""
    result = {"elapsed": 0}
    start = time.perf_counter()
    try:
        yield result
    finally:
        result["elapsed"] = time.perf_counter() - start


def benchmark(func, iterations=1000, warmup=100):
    """Run a benchmark function multiple times and return statistics."""
    # Warmup
    for _ in range(warmup):
        func()

    # Actual benchmark
    times = []
    for _ in range(iterations):
        with timer() as t:
            func()
        times.append(t["elapsed"])

    times.sort()
    return {
        "min": times[0],
        "max": times[-1],
        "mean": sum(times) / len(times),
        "median": times[len(times) // 2],
        "p95": times[int(len(times) * 0.95)],
        "iterations": iterations,
    }


# Test data generators
def make_small_strings(count=100):
    """Small strings that fit in stack allocation (<=256 bytes)."""
    return ["hello world " * 5 for _ in range(count)]


def make_large_strings(count=20):
    """Large strings that require heap allocation."""
    return ["x" * 1000 for _ in range(count)]


def make_many_small_values(count=1000):
    """Many small integers - tests read call overhead."""
    return list(range(count))


def make_nested_structure():
    """Complex nested structure."""
    return {
        "users": [
            {
                "id": i,
                "name": f"User {i}",
                "email": f"user{i}@example.com",
                "active": i % 2 == 0,
                "score": i * 1.5,
                "tags": [f"tag{j}" for j in range(5)],
            }
            for i in range(50)
        ],
        "metadata": {
            "total": 50,
            "page": 1,
            "version": "1.0.0",
        },
    }


def make_binary_data():
    """Binary data blob."""
    return {"data": bytes(range(256)) * 10}


TEST_DATA = {
    "small_strings": make_small_strings(),
    "large_strings": make_large_strings(),
    "many_small_values": make_many_small_values(),
    "nested_structure": make_nested_structure(),
    "binary_data": make_binary_data(),
}


def benchmark_loads(data_name, iterations=1000):
    """Benchmark cbor2.loads() on bytes."""
    data = TEST_DATA[data_name]
    encoded = cbor2.dumps(data)

    def run():
        cbor2.loads(encoded)

    return benchmark(run, iterations)


def benchmark_streaming(data_name, read_size=None, iterations=1000):
    """Benchmark streaming decode with CBORDecoder."""
    data = TEST_DATA[data_name]
    encoded = cbor2.dumps(data)

    def run():
        fp = io.BytesIO(encoded)
        if read_size is not None:
            decoder = cbor2.CBORDecoder(fp, read_size=read_size)
        else:
            decoder = cbor2.CBORDecoder(fp)
        decoder.decode()

    return benchmark(run, iterations)


def benchmark_streaming_multiple(count=100, read_size=None, iterations=100):
    """Benchmark decoding multiple values from a stream."""
    # Create a stream with multiple encoded values
    values = [{"index": i, "data": f"value_{i}"} for i in range(count)]
    encoded = b"".join(cbor2.dumps(v) for v in values)

    def run():
        fp = io.BytesIO(encoded)
        if read_size is not None:
            decoder = cbor2.CBORDecoder(fp, read_size=read_size)
        else:
            decoder = cbor2.CBORDecoder(fp)
        results = []
        for _ in range(count):
            results.append(decoder.decode())

    return benchmark(run, iterations)


def run_all_benchmarks():
    """Run all benchmarks and return results."""
    results = {
        "version_info": get_version_info(),
        "benchmarks": {},
    }

    print(f"cbor2 version: {results['version_info']['version']}")
    print(f"C extension: {results['version_info']['c_extension']}")
    print()

    # Benchmark loads() for each data type
    print("=== loads() benchmarks ===")
    for data_name in TEST_DATA:
        print(f"  {data_name}...", end=" ", flush=True)
        result = benchmark_loads(data_name)
        results["benchmarks"][f"loads_{data_name}"] = result
        print(f"{result['mean']*1000:.3f}ms mean")

    # Benchmark streaming with default read_size
    print("\n=== Streaming decode (default read_size) ===")
    for data_name in TEST_DATA:
        print(f"  {data_name}...", end=" ", flush=True)
        result = benchmark_streaming(data_name)
        results["benchmarks"][f"streaming_default_{data_name}"] = result
        print(f"{result['mean']*1000:.3f}ms mean")

    # Benchmark streaming with different read_size values
    # Only test if read_size parameter is supported
    try:
        test_fp = io.BytesIO(cbor2.dumps(1))
        cbor2.CBORDecoder(test_fp, read_size=4096)
        has_read_size = True
    except TypeError:
        has_read_size = False
        print("\n(read_size parameter not supported in this version)")

    if has_read_size:
        for read_size in [1, 64, 256, 1024, 4096]:
            print(f"\n=== Streaming decode (read_size={read_size}) ===")
            for data_name in TEST_DATA:
                print(f"  {data_name}...", end=" ", flush=True)
                result = benchmark_streaming(data_name, read_size=read_size)
                results["benchmarks"][f"streaming_rs{read_size}_{data_name}"] = result
                print(f"{result['mean']*1000:.3f}ms mean")

        # Multiple values from stream
        print("\n=== Multiple values from stream ===")
        for read_size in [None, 1, 4096]:
            label = f"read_size={read_size}" if read_size else "default"
            print(f"  100 values ({label})...", end=" ", flush=True)
            result = benchmark_streaming_multiple(100, read_size=read_size)
            rs_key = f"rs{read_size}" if read_size else "default"
            results["benchmarks"][f"multi_stream_{rs_key}"] = result
            print(f"{result['mean']*1000:.3f}ms mean")

    return results


def compare_results(baseline_file, current_file):
    """Compare two benchmark result files."""
    with open(baseline_file) as f:
        baseline = json.load(f)
    with open(current_file) as f:
        current = json.load(f)

    print("=" * 70)
    print("BENCHMARK COMPARISON")
    print("=" * 70)
    print(f"Baseline: {baseline['version_info']['version']} "
          f"(C ext: {baseline['version_info']['c_extension']})")
    print(f"Current:  {current['version_info']['version']} "
          f"(C ext: {current['version_info']['c_extension']})")
    print("=" * 70)
    print()
    print(f"{'Benchmark':<45} {'Baseline':>10} {'Current':>10} {'Change':>10}")
    print("-" * 70)

    for key in sorted(baseline["benchmarks"].keys()):
        if key not in current["benchmarks"]:
            continue

        base_mean = baseline["benchmarks"][key]["mean"] * 1000
        curr_mean = current["benchmarks"][key]["mean"] * 1000

        if base_mean > 0:
            change = ((curr_mean - base_mean) / base_mean) * 100
            change_str = f"{change:+.1f}%"
            if change < -5:
                change_str = f"\033[32m{change_str}\033[0m"  # Green for improvement
            elif change > 5:
                change_str = f"\033[31m{change_str}\033[0m"  # Red for regression
        else:
            change_str = "N/A"

        print(f"{key:<45} {base_mean:>9.3f}ms {curr_mean:>9.3f}ms {change_str:>10}")

    # Print benchmarks only in current (new features)
    new_benchmarks = set(current["benchmarks"].keys()) - set(baseline["benchmarks"].keys())
    if new_benchmarks:
        print()
        print("New benchmarks (not in baseline):")
        print("-" * 70)
        for key in sorted(new_benchmarks):
            curr_mean = current["benchmarks"][key]["mean"] * 1000
            print(f"{key:<45} {'-':>10} {curr_mean:>9.3f}ms")


def main():
    parser = argparse.ArgumentParser(description="Benchmark cbor2 performance")
    parser.add_argument("--output", "-o", help="Output JSON file for results")
    parser.add_argument("--compare", "-c", nargs=2, metavar=("BASELINE", "CURRENT"),
                        help="Compare two result files")
    args = parser.parse_args()

    if args.compare:
        compare_results(args.compare[0], args.compare[1])
        return

    results = run_all_benchmarks()

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {args.output}")
    else:
        print("\nTip: Use --output to save results for comparison")


if __name__ == "__main__":
    main()
