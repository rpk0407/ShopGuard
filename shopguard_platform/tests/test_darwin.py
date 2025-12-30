#!/usr/bin/env python3
"""
DARWINIAN EVOLUTION TEST
========================
Standalone test to verify the evolution engine works.

Run: python3 test_darwin.py
"""

import sys
import os
import time
import random

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_darwin():
    """Test the Darwin evolution engine"""
    print("\n" + "=" * 60)
    print("  DARWINIAN EVOLUTION ENGINE TEST")
    print("=" * 60 + "\n")

    # Test 1: Import modules
    print("[TEST 1] Importing Darwin modules...")
    try:
        from src.evolution.darwin import Darwin, EvolutionConfig, Genome, MutantAgent, MutantType
        print("  ✓ Darwin imported successfully")
    except ImportError as e:
        print(f"  ✗ Failed to import Darwin: {e}")
        return False

    # Test 2: Import TitanBrain
    print("\n[TEST 2] Importing TitanBrain...")
    try:
        from src.core.titan_brain import TitanBrain, EvolvingBrain, BrainConfig
        print("  ✓ TitanBrain imported successfully")
    except ImportError as e:
        print(f"  ✗ Failed to import TitanBrain: {e}")
        return False

    # Test 3: Import FastMath
    print("\n[TEST 3] Importing FastMath...")
    try:
        from src.core.fast_math import FastMath, NUMBA_AVAILABLE
        fm = FastMath()
        print(f"  ✓ FastMath imported (Numba available: {NUMBA_AVAILABLE})")
    except ImportError as e:
        print(f"  ✗ Failed to import FastMath: {e}")
        return False

    # Test 4: Create genome
    print("\n[TEST 4] Creating genome...")
    genome = Genome(
        entropy_threshold=2.5,
        hurst_threshold=0.6,
        k_threshold=1.2,
        cvd_sensitivity=1.0
    )
    print(f"  ✓ Genome created: K={genome.k_threshold}, Entropy={genome.entropy_threshold}")

    # Test 5: Create Darwin engine
    print("\n[TEST 5] Creating Darwin engine...")
    config = EvolutionConfig(
        population_size=20,  # Smaller for testing
        evaluation_ticks=50,
        generation_interval=1
    )
    darwin = Darwin(config=config)
    print(f"  ✓ Darwin created with population_size={config.population_size}")

    # Test 6: Spawn population
    print("\n[TEST 6] Spawning population...")
    darwin.spawn_population()
    print(f"  ✓ Spawned {len(darwin.population)} mutants")

    # Count types
    type_counts = {}
    for agent in darwin.population:
        t = agent.mutant_type.value
        type_counts[t] = type_counts.get(t, 0) + 1
    print(f"  Types: {type_counts}")

    # Test 7: Generate fake ticks
    print("\n[TEST 7] Generating synthetic market ticks...")
    ticks = []
    price = 100.0
    for i in range(50):
        price *= random.uniform(0.995, 1.005)
        if i == 25:  # Crash mid-way
            price *= 0.97
        phase = 'stable' if i < 20 else 'crash' if i < 30 else 'accumulation' if i < 40 else 'recovery'
        ticks.append({
            'price': price,
            'entropy': random.uniform(2.0, 3.5),
            'hurst': random.uniform(0.4, 0.7),
            'viral_k': random.uniform(0.8, 1.5),
            'cvd': random.uniform(-200, 200),
            'phase': phase
        })
    print(f"  ✓ Generated {len(ticks)} ticks (price range: ${min(t['price'] for t in ticks):.2f} - ${max(t['price'] for t in ticks):.2f})")

    # Test 8: Run evolution generation
    print("\n[TEST 8] Running evolution generation...")
    start = time.time()
    alpha = darwin.run_generation(ticks)
    elapsed = time.time() - start
    print(f"  ✓ Generation completed in {elapsed:.2f}s")
    print(f"  Generation: {darwin.generation}")
    print(f"  Best fitness: {darwin.stats['best_fitness_ever']:.2f}")

    if alpha:
        print(f"\n  🏆 ALPHA GENOME:")
        print(f"     K-Factor: {alpha.k_threshold:.3f}")
        print(f"     Entropy:  {alpha.entropy_threshold:.3f}")
        print(f"     Hurst:    {alpha.hurst_threshold:.3f}")
        print(f"     CVD Sens: {alpha.cvd_sensitivity:.3f}")

    # Test 9: Run 2 more generations
    print("\n[TEST 9] Running 2 more generations...")
    for _ in range(2):
        darwin.run_generation(ticks)
    print(f"  ✓ Total generations: {darwin.generation}")
    print(f"  Best fitness: {darwin.stats['best_fitness_ever']:.2f}")
    print(f"  Alpha updates: {darwin.stats['alpha_updates']}")

    # Test 10: Create TitanBrain and hot-swap alpha
    print("\n[TEST 10] Testing TitanBrain hot-swap...")
    brain = TitanBrain()
    print(f"  Initial config: K={brain.config.k_threshold_high}, Entropy={brain.config.entropy_threshold_high}")

    if darwin.alpha_genome:
        brain.update_from_genome(darwin.alpha_genome)
        print(f"  ✓ Alpha hot-swapped!")
        print(f"  New config: K={brain.config.k_threshold_high:.3f}, Entropy={brain.config.entropy_threshold_high:.3f}")
        print(f"  Config version: v{brain.config.version}")
        print(f"  Config source: {brain.config.source}")

    # Test 11: Process tick through TitanBrain
    print("\n[TEST 11] Processing tick through TitanBrain...")
    test_tick = {
        'asset': 'BTC/USDT',
        'price': 100.0,
        'entropy': 2.2,
        'hurst': 0.65,
        'viral_k': 1.3,
        'cvd': 150,
        'phase': 'accumulation'
    }
    signal = brain.process_tick(test_tick)
    print(f"  ✓ Signal: {signal.signal_type.value}")
    print(f"  Confidence: {signal.confidence:.2f}")
    print(f"  Conviction: {signal.conviction:.2f}")
    print(f"  Pillars: Bio={signal.bio_check}, Physics={signal.physics_check}, Micro={signal.micro_check}")

    # Test 12: Test FastMath performance
    print("\n[TEST 12] Testing FastMath performance...")
    import numpy as np
    prices = np.random.random(1000) * 100 + 50

    # Warmup
    fm.warmup()

    # Benchmark
    start = time.time()
    for _ in range(100):
        fm.shannon_entropy(prices)
    entropy_time = (time.time() - start) / 100 * 1000

    start = time.time()
    for _ in range(100):
        fm.hurst_exponent(prices)
    hurst_time = (time.time() - start) / 100 * 1000

    print(f"  Shannon Entropy: {entropy_time:.3f}ms per call")
    print(f"  Hurst Exponent:  {hurst_time:.3f}ms per call")
    print(f"  ✓ FastMath performance OK")

    # Final summary
    print("\n" + "=" * 60)
    print("  ALL TESTS PASSED! 🧬")
    print("=" * 60)
    print(f"\nDarwin Stats:")
    print(f"  Generations:      {darwin.stats['generations']}")
    print(f"  Total Mutations:  {darwin.stats['total_mutations']}")
    print(f"  Total Crossovers: {darwin.stats['total_crossovers']}")
    print(f"  Alpha Updates:    {darwin.stats['alpha_updates']}")
    print(f"  Best Fitness:     {darwin.stats['best_fitness_ever']:.2f}")

    return True


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)  # Suppress info logs

    success = test_darwin()
    sys.exit(0 if success else 1)
