"""
DARWINIAN EVOLUTION ENGINE
==========================
Genetic Algorithm layer that runs parallel simulations to evolve optimal
trading parameters. The strong survive. The weak are culled.

Architecture:
    - Population of 50 Mutant Agents with randomized genomes
    - Each agent runs in the Matrix simulator
    - Fitness = Simulated P&L over evaluation period
    - Bottom 50% culled every generation
    - Top 50% breed via crossover + mutation
    - Alpha Mutant's genome hot-swapped into live TitanBrain
"""

import random
import time
import threading
import logging
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Callable, Any
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy

logger = logging.getLogger(__name__)


class MutantType(Enum):
    """Classification of mutant trading styles"""
    AGGRESSIVE = "aggressive"      # Low thresholds, high frequency
    CONSERVATIVE = "conservative"  # High thresholds, low frequency
    BALANCED = "balanced"          # Middle ground
    CHAOTIC = "chaotic"           # Random mutations
    ALPHA = "alpha"               # Current best performer


@dataclass
class Genome:
    """
    The DNA of a trading agent.
    Each gene represents a threshold or sensitivity parameter.
    """
    # Bio-Check: Shannon Entropy threshold
    entropy_threshold: float = 2.5      # Below this = order detected
    entropy_weight: float = 1.0         # Importance multiplier

    # Physics-Check: Hurst Exponent threshold
    hurst_threshold: float = 0.6        # Above this = trending
    hurst_weight: float = 1.0

    # Micro-Check: Viral K-Factor threshold
    k_threshold: float = 1.2            # Above this = viral spread
    k_weight: float = 1.0

    # CVD sensitivity
    cvd_sensitivity: float = 1.0        # Whale activity multiplier
    cvd_reversal_threshold: float = 100 # CVD reversal detection

    # Position sizing genes
    position_size_base: float = 0.1     # Base position as % of capital
    position_size_conviction: float = 0.05  # Extra % per conviction point

    # Risk management genes
    stop_loss_atr_mult: float = 2.0     # Stop loss = ATR * this
    take_profit_atr_mult: float = 3.0   # Take profit = ATR * this
    max_drawdown_pct: float = 0.15      # Max drawdown before shutdown

    # Timing genes
    entry_delay_ticks: int = 2          # Wait N ticks after signal
    exit_speed: float = 1.0             # Exit urgency multiplier

    # Meta
    generation: int = 0
    parent_ids: List[str] = field(default_factory=list)
    mutation_rate: float = 0.1

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'Genome':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def clone(self) -> 'Genome':
        return copy.deepcopy(self)


@dataclass
class MutantAgent:
    """
    A single mutant agent running in the simulation.
    Lives or dies based on fitness.
    """
    id: str
    genome: Genome
    mutant_type: MutantType

    # Performance tracking
    fitness: float = 0.0
    total_pnl: float = 0.0
    trades: int = 0
    wins: int = 0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0

    # State
    is_alive: bool = True
    capital: float = 10000.0
    position: float = 0.0
    entry_price: float = 0.0

    # History
    pnl_history: List[float] = field(default_factory=list)
    trade_history: List[Dict] = field(default_factory=list)

    def calculate_fitness(self) -> float:
        """
        Fitness function: Weighted combination of metrics.
        Higher is better. Negative fitness = death.
        """
        if not self.pnl_history:
            return 0.0

        # Core metrics
        total_return = self.total_pnl / 10000.0  # % return
        win_rate = self.wins / max(self.trades, 1)

        # Risk-adjusted return (pseudo-Sharpe)
        if len(self.pnl_history) > 1:
            import statistics
            mean_pnl = statistics.mean(self.pnl_history)
            std_pnl = statistics.stdev(self.pnl_history) if len(self.pnl_history) > 1 else 1
            self.sharpe_ratio = mean_pnl / max(std_pnl, 0.001)
        else:
            self.sharpe_ratio = 0

        # Fitness formula: Reward returns, penalize drawdown
        self.fitness = (
            total_return * 100 +                    # Raw returns
            win_rate * 20 +                         # Win rate bonus
            self.sharpe_ratio * 10 -                # Risk-adjusted bonus
            self.max_drawdown * 50 -                # Drawdown penalty
            (0 if self.trades > 5 else 10)          # Activity penalty
        )

        return self.fitness

    def process_tick(self, tick: Dict) -> Optional[Dict]:
        """
        Process a market tick and make trading decision.
        Returns trade action if any.
        """
        if not self.is_alive:
            return None

        price = tick.get('price', 0)
        entropy = tick.get('entropy', 3.0)
        hurst = tick.get('hurst', 0.5)
        viral_k = tick.get('viral_k', 1.0)
        cvd = tick.get('cvd', 0)
        phase = tick.get('phase', 'stable')

        genome = self.genome
        action = None

        # Calculate conviction score based on genome thresholds
        conviction = 0

        if entropy < genome.entropy_threshold:
            conviction += genome.entropy_weight
        if hurst > genome.hurst_threshold:
            conviction += genome.hurst_weight
        if viral_k > genome.k_threshold:
            conviction += genome.k_weight
        if cvd > genome.cvd_reversal_threshold:
            conviction += genome.cvd_sensitivity * 0.5

        # Normalize conviction to 0-1
        max_conviction = genome.entropy_weight + genome.hurst_weight + genome.k_weight + genome.cvd_sensitivity
        conviction_pct = conviction / max(max_conviction, 1)

        # Entry logic
        if self.position == 0:
            if conviction_pct > 0.6 and phase in ['accumulation', 'recovery']:
                # Calculate position size
                size_pct = genome.position_size_base + (conviction_pct * genome.position_size_conviction)
                position_value = self.capital * size_pct
                self.position = position_value / price
                self.entry_price = price
                self.trades += 1

                action = {
                    'type': 'ENTRY',
                    'side': 'LONG',
                    'price': price,
                    'size': self.position,
                    'conviction': conviction_pct
                }

        # Exit logic
        elif self.position > 0:
            pnl_pct = (price - self.entry_price) / self.entry_price

            # Stop loss
            if pnl_pct < -genome.stop_loss_atr_mult * 0.01:
                self._close_position(price, 'STOP_LOSS')
                action = {'type': 'EXIT', 'reason': 'STOP_LOSS', 'price': price}

            # Take profit
            elif pnl_pct > genome.take_profit_atr_mult * 0.01:
                self._close_position(price, 'TAKE_PROFIT')
                action = {'type': 'EXIT', 'reason': 'TAKE_PROFIT', 'price': price}

            # Conviction exit
            elif conviction_pct < 0.3 or phase == 'crash':
                self._close_position(price, 'CONVICTION_DROP')
                action = {'type': 'EXIT', 'reason': 'CONVICTION_DROP', 'price': price}

        # Update equity curve
        current_equity = self.capital + (self.position * price if self.position > 0 else 0)
        peak_equity = max(self.pnl_history) + 10000 if self.pnl_history else 10000
        drawdown = (peak_equity - current_equity) / peak_equity
        self.max_drawdown = max(self.max_drawdown, drawdown)

        # Kill if max drawdown exceeded
        if drawdown > genome.max_drawdown_pct:
            self.is_alive = False
            self._close_position(price, 'MAX_DRAWDOWN')

        return action

    def _close_position(self, price: float, reason: str):
        """Close current position and record P&L"""
        if self.position > 0:
            pnl = (price - self.entry_price) * self.position
            self.total_pnl += pnl
            self.capital += pnl
            self.pnl_history.append(pnl)

            if pnl > 0:
                self.wins += 1

            self.trade_history.append({
                'entry': self.entry_price,
                'exit': price,
                'pnl': pnl,
                'reason': reason
            })

            self.position = 0
            self.entry_price = 0


@dataclass
class EvolutionConfig:
    """Configuration for the Darwinian engine"""
    population_size: int = 50
    survivors_pct: float = 0.5          # Top 50% survive
    mutation_rate: float = 0.15
    mutation_strength: float = 0.2      # Max % change per mutation
    crossover_rate: float = 0.7
    elite_count: int = 2                # Top N copied unchanged
    evaluation_ticks: int = 300         # Ticks per evaluation (10 min at 2s/tick)
    generation_interval: int = 600      # Seconds between generations
    hot_swap_interval: int = 3600       # Seconds between live updates (1 hour)


class Darwin:
    """
    THE DARWINIAN ENGINE
    ====================
    Evolves trading parameters through natural selection.

    The strong survive. The weak are culled. Evolution never stops.
    """

    def __init__(self, config: EvolutionConfig = None, matrix=None):
        self.config = config or EvolutionConfig()
        self.matrix = matrix
        self.population: List[MutantAgent] = []
        self.generation = 0
        self.alpha_genome: Optional[Genome] = None
        self.alpha_history: List[Genome] = []

        # Callbacks
        self.on_generation_complete: Optional[Callable] = None
        self.on_alpha_evolved: Optional[Callable] = None

        # Threading
        self._running = False
        self._evolution_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Stats
        self.stats = {
            'generations': 0,
            'total_mutations': 0,
            'total_crossovers': 0,
            'alpha_updates': 0,
            'best_fitness_ever': 0,
            'avg_fitness_history': []
        }

        logger.info("🧬 Darwin Engine initialized")

    def spawn_population(self):
        """Create initial population with diverse genomes"""
        self.population = []

        for i in range(self.config.population_size):
            # Determine mutant type distribution
            if i < self.config.population_size * 0.2:
                mutant_type = MutantType.AGGRESSIVE
                genome = self._create_aggressive_genome()
            elif i < self.config.population_size * 0.4:
                mutant_type = MutantType.CONSERVATIVE
                genome = self._create_conservative_genome()
            elif i < self.config.population_size * 0.7:
                mutant_type = MutantType.BALANCED
                genome = self._create_balanced_genome()
            else:
                mutant_type = MutantType.CHAOTIC
                genome = self._create_chaotic_genome()

            agent = MutantAgent(
                id=f"mutant_{self.generation}_{i}",
                genome=genome,
                mutant_type=mutant_type
            )
            self.population.append(agent)

        logger.info(f"🧬 Spawned {len(self.population)} mutants (Gen {self.generation})")

    def _create_aggressive_genome(self) -> Genome:
        """Create aggressive trading genome (low thresholds)"""
        return Genome(
            entropy_threshold=random.uniform(2.8, 3.5),
            hurst_threshold=random.uniform(0.45, 0.55),
            k_threshold=random.uniform(1.0, 1.15),
            cvd_sensitivity=random.uniform(1.2, 1.8),
            position_size_base=random.uniform(0.15, 0.25),
            stop_loss_atr_mult=random.uniform(1.5, 2.0),
            take_profit_atr_mult=random.uniform(2.0, 3.0),
            generation=self.generation
        )

    def _create_conservative_genome(self) -> Genome:
        """Create conservative trading genome (high thresholds)"""
        return Genome(
            entropy_threshold=random.uniform(1.8, 2.3),
            hurst_threshold=random.uniform(0.65, 0.75),
            k_threshold=random.uniform(1.4, 1.7),
            cvd_sensitivity=random.uniform(0.6, 1.0),
            position_size_base=random.uniform(0.05, 0.1),
            stop_loss_atr_mult=random.uniform(2.5, 3.5),
            take_profit_atr_mult=random.uniform(4.0, 6.0),
            generation=self.generation
        )

    def _create_balanced_genome(self) -> Genome:
        """Create balanced trading genome"""
        return Genome(
            entropy_threshold=random.uniform(2.3, 2.7),
            hurst_threshold=random.uniform(0.55, 0.65),
            k_threshold=random.uniform(1.15, 1.35),
            cvd_sensitivity=random.uniform(0.9, 1.2),
            position_size_base=random.uniform(0.08, 0.15),
            stop_loss_atr_mult=random.uniform(2.0, 2.5),
            take_profit_atr_mult=random.uniform(3.0, 4.0),
            generation=self.generation
        )

    def _create_chaotic_genome(self) -> Genome:
        """Create fully randomized genome"""
        return Genome(
            entropy_threshold=random.uniform(1.5, 4.0),
            hurst_threshold=random.uniform(0.4, 0.8),
            k_threshold=random.uniform(0.8, 2.0),
            cvd_sensitivity=random.uniform(0.3, 2.0),
            position_size_base=random.uniform(0.03, 0.3),
            stop_loss_atr_mult=random.uniform(1.0, 4.0),
            take_profit_atr_mult=random.uniform(1.5, 8.0),
            max_drawdown_pct=random.uniform(0.1, 0.25),
            generation=self.generation
        )

    def evaluate_population(self, ticks: List[Dict]) -> List[MutantAgent]:
        """
        Run all mutants through the simulation and evaluate fitness.
        Returns sorted population (best first).
        """
        logger.info(f"🧬 Evaluating {len(self.population)} mutants over {len(ticks)} ticks...")

        # Process all ticks for each mutant
        for tick in ticks:
            for agent in self.population:
                if agent.is_alive:
                    agent.process_tick(tick)

        # Calculate fitness scores
        for agent in self.population:
            agent.calculate_fitness()

        # Sort by fitness (descending)
        self.population.sort(key=lambda a: a.fitness, reverse=True)

        # Log top performers
        top_3 = self.population[:3]
        for i, agent in enumerate(top_3):
            logger.info(
                f"  #{i+1} {agent.id}: Fitness={agent.fitness:.2f}, "
                f"P&L=${agent.total_pnl:.2f}, Trades={agent.trades}, "
                f"WinRate={agent.wins/max(agent.trades,1)*100:.1f}%"
            )

        return self.population

    def select_survivors(self) -> List[MutantAgent]:
        """Kill bottom 50%, return survivors"""
        cutoff = int(len(self.population) * self.config.survivors_pct)
        survivors = self.population[:cutoff]
        culled = self.population[cutoff:]

        for agent in culled:
            agent.is_alive = False

        logger.info(f"🧬 Natural selection: {len(survivors)} survived, {len(culled)} culled")
        return survivors

    def crossover(self, parent_a: Genome, parent_b: Genome) -> Genome:
        """
        Sexual reproduction: Create child genome from two parents.
        Uses uniform crossover with some gene-level mixing.
        """
        child = Genome(generation=self.generation)

        # For each gene, randomly pick from parent A or B
        genes = [
            'entropy_threshold', 'entropy_weight',
            'hurst_threshold', 'hurst_weight',
            'k_threshold', 'k_weight',
            'cvd_sensitivity', 'cvd_reversal_threshold',
            'position_size_base', 'position_size_conviction',
            'stop_loss_atr_mult', 'take_profit_atr_mult',
            'max_drawdown_pct', 'entry_delay_ticks', 'exit_speed'
        ]

        for gene in genes:
            if random.random() < 0.5:
                setattr(child, gene, getattr(parent_a, gene))
            else:
                setattr(child, gene, getattr(parent_b, gene))

        child.parent_ids = [f"gen{parent_a.generation}", f"gen{parent_b.generation}"]
        self.stats['total_crossovers'] += 1

        return child

    def mutate(self, genome: Genome) -> Genome:
        """
        Random mutation: Slightly modify genome values.
        Mutation strength determines max % change.
        """
        mutated = genome.clone()
        mutated.generation = self.generation

        mutation_targets = {
            'entropy_threshold': (1.5, 4.0),
            'hurst_threshold': (0.4, 0.8),
            'k_threshold': (0.8, 2.0),
            'cvd_sensitivity': (0.3, 2.0),
            'position_size_base': (0.03, 0.3),
            'stop_loss_atr_mult': (1.0, 4.0),
            'take_profit_atr_mult': (1.5, 8.0),
            'max_drawdown_pct': (0.05, 0.3)
        }

        for gene, (min_val, max_val) in mutation_targets.items():
            if random.random() < self.config.mutation_rate:
                current = getattr(mutated, gene)
                # Apply random mutation within strength bounds
                delta = current * self.config.mutation_strength * random.uniform(-1, 1)
                new_val = max(min_val, min(max_val, current + delta))
                setattr(mutated, gene, new_val)
                self.stats['total_mutations'] += 1

        mutated.mutation_rate = genome.mutation_rate
        return mutated

    def breed_next_generation(self, survivors: List[MutantAgent]):
        """
        Create new population from survivors through breeding.
        """
        new_population = []

        # Elite: Copy top performers unchanged
        for i in range(min(self.config.elite_count, len(survivors))):
            elite = MutantAgent(
                id=f"elite_{self.generation}_{i}",
                genome=survivors[i].genome.clone(),
                mutant_type=MutantType.ALPHA
            )
            new_population.append(elite)

        # Breed rest of population
        while len(new_population) < self.config.population_size:
            # Tournament selection: Pick 2 random survivors, take better one
            parent_a = self._tournament_select(survivors)
            parent_b = self._tournament_select(survivors)

            # Crossover
            if random.random() < self.config.crossover_rate:
                child_genome = self.crossover(parent_a.genome, parent_b.genome)
            else:
                child_genome = parent_a.genome.clone()

            # Mutation
            child_genome = self.mutate(child_genome)

            # Determine type based on genome characteristics
            mutant_type = self._classify_genome(child_genome)

            child = MutantAgent(
                id=f"mutant_{self.generation}_{len(new_population)}",
                genome=child_genome,
                mutant_type=mutant_type
            )
            new_population.append(child)

        self.population = new_population
        logger.info(f"🧬 Bred generation {self.generation}: {len(new_population)} mutants")

    def _tournament_select(self, candidates: List[MutantAgent], k: int = 3) -> MutantAgent:
        """Tournament selection: Pick best of k random candidates"""
        tournament = random.sample(candidates, min(k, len(candidates)))
        return max(tournament, key=lambda a: a.fitness)

    def _classify_genome(self, genome: Genome) -> MutantType:
        """Classify genome based on its characteristics"""
        aggression_score = (
            (3.0 - genome.entropy_threshold) / 1.5 +
            (genome.k_threshold - 1.0) / 0.5 +
            genome.position_size_base / 0.15
        ) / 3

        if aggression_score > 0.7:
            return MutantType.AGGRESSIVE
        elif aggression_score < 0.3:
            return MutantType.CONSERVATIVE
        else:
            return MutantType.BALANCED

    def get_alpha(self) -> Optional[Genome]:
        """Get the current best-performing genome"""
        if not self.population:
            return self.alpha_genome

        best = max(self.population, key=lambda a: a.fitness)

        if best.fitness > self.stats['best_fitness_ever']:
            self.stats['best_fitness_ever'] = best.fitness
            self.alpha_genome = best.genome.clone()
            self.alpha_history.append(self.alpha_genome)
            self.stats['alpha_updates'] += 1

            logger.info(f"🧬🏆 NEW ALPHA: Fitness={best.fitness:.2f}")

            if self.on_alpha_evolved:
                self.on_alpha_evolved(self.alpha_genome)

        return self.alpha_genome

    def run_generation(self, ticks: List[Dict]):
        """Run a single generation of evolution"""
        self.generation += 1

        logger.info(f"\n{'='*50}")
        logger.info(f"🧬 GENERATION {self.generation} BEGINS")
        logger.info(f"{'='*50}")

        # If first generation, spawn population
        if not self.population:
            self.spawn_population()

        # Evaluate all mutants
        self.evaluate_population(ticks)

        # Natural selection
        survivors = self.select_survivors()

        # Get alpha before breeding
        alpha = self.get_alpha()

        # Breed next generation
        self.breed_next_generation(survivors)

        # Update stats
        self.stats['generations'] = self.generation
        avg_fitness = sum(a.fitness for a in self.population) / len(self.population)
        self.stats['avg_fitness_history'].append(avg_fitness)

        if self.on_generation_complete:
            self.on_generation_complete(self.generation, self.stats)

        logger.info(f"🧬 Generation {self.generation} complete. Avg Fitness: {avg_fitness:.2f}")

        return alpha

    def start_evolution(self, matrix=None):
        """Start continuous evolution in background thread"""
        if self._running:
            logger.warning("Evolution already running")
            return

        self.matrix = matrix or self.matrix
        if not self.matrix:
            raise ValueError("Matrix simulator required for evolution")

        self._running = True
        self._evolution_thread = threading.Thread(target=self._evolution_loop, daemon=True)
        self._evolution_thread.start()

        logger.info("🧬 Darwinian evolution STARTED")

    def stop_evolution(self):
        """Stop the evolution loop"""
        self._running = False
        if self._evolution_thread:
            self._evolution_thread.join(timeout=5)
        logger.info("🧬 Darwinian evolution STOPPED")

    def _evolution_loop(self):
        """Main evolution loop running in background"""
        while self._running:
            try:
                # Generate ticks from Matrix
                ticks = []
                for _ in range(self.config.evaluation_ticks):
                    if not self._running:
                        break
                    tick = self.matrix.tick("BTC/USDT")
                    ticks.append(tick)
                    time.sleep(0.01)  # Fast-forward simulation

                if not self._running:
                    break

                # Run generation
                with self._lock:
                    self.run_generation(ticks)

                # Wait for next generation
                time.sleep(self.config.generation_interval)

            except Exception as e:
                logger.error(f"Evolution error: {e}")
                time.sleep(10)

    def get_stats(self) -> Dict:
        """Get evolution statistics"""
        return {
            **self.stats,
            'population_size': len(self.population),
            'alpha_genome': self.alpha_genome.to_dict() if self.alpha_genome else None,
            'is_running': self._running
        }

    def export_alpha(self, path: str):
        """Export alpha genome to file"""
        if self.alpha_genome:
            with open(path, 'w') as f:
                json.dump(self.alpha_genome.to_dict(), f, indent=2)
            logger.info(f"🧬 Alpha genome exported to {path}")

    def import_genome(self, path: str) -> Genome:
        """Import genome from file"""
        with open(path, 'r') as f:
            data = json.load(f)
        return Genome.from_dict(data)


# =============================================================================
# OPTIMIZED CONFIG OUTPUT
# =============================================================================

@dataclass
class OptimizedConfig:
    """
    Configuration output from Darwin to TitanBrain.
    This is what gets hot-swapped into the live system.
    """
    # Thresholds
    entropy_threshold: float
    hurst_threshold: float
    k_threshold: float
    cvd_sensitivity: float

    # Position sizing
    position_size_base: float
    position_size_conviction: float

    # Risk management
    stop_loss_atr_mult: float
    take_profit_atr_mult: float
    max_drawdown_pct: float

    # Meta
    generation: int
    fitness_score: float
    timestamp: float

    @classmethod
    def from_genome(cls, genome: Genome, fitness: float) -> 'OptimizedConfig':
        return cls(
            entropy_threshold=genome.entropy_threshold,
            hurst_threshold=genome.hurst_threshold,
            k_threshold=genome.k_threshold,
            cvd_sensitivity=genome.cvd_sensitivity,
            position_size_base=genome.position_size_base,
            position_size_conviction=genome.position_size_conviction,
            stop_loss_atr_mult=genome.stop_loss_atr_mult,
            take_profit_atr_mult=genome.take_profit_atr_mult,
            max_drawdown_pct=genome.max_drawdown_pct,
            generation=genome.generation,
            fitness_score=fitness,
            timestamp=time.time()
        )


if __name__ == "__main__":
    # Test evolution without Matrix
    logging.basicConfig(level=logging.INFO)

    darwin = Darwin()
    darwin.spawn_population()

    # Generate fake ticks
    fake_ticks = []
    price = 100.0
    for i in range(300):
        price *= random.uniform(0.995, 1.005)
        phase = 'stable' if i < 100 else 'crash' if i < 150 else 'accumulation' if i < 200 else 'recovery'
        fake_ticks.append({
            'price': price,
            'entropy': random.uniform(2.0, 3.5),
            'hurst': random.uniform(0.4, 0.7),
            'viral_k': random.uniform(0.8, 1.5),
            'cvd': random.uniform(-200, 200),
            'phase': phase
        })

    # Run 3 generations
    for _ in range(3):
        darwin.run_generation(fake_ticks)

    print(f"\nFinal Alpha: {darwin.alpha_genome}")
    print(f"Stats: {darwin.get_stats()}")
