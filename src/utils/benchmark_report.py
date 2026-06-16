"""
Benchmark Report Generator for LLM_robot_2.

Automatically generates comprehensive benchmark reports from mission logs,
LLM metrics, and test results.

Story: 2.5 - Monitoring, Logging, and Evaluation
AC #4: Generate benchmark reports with cost/latency analysis and performance metrics
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger


class BenchmarkReport:
    """
    Automated benchmark report generator.

    Aggregates data from:
    - JSON mission logs (from Loguru)
    - OpenLit LLM metrics (if available)
    - pytest evaluation results

    Generates:
    - Markdown report with tables and statistics
    - Performance metrics (success rate, execution time, replan count)
    - LLM usage statistics (calls, tokens, cost, latency)
    """

    def __init__(self, log_dir: str = "logs"):
        """
        Initialize benchmark report generator.

        Args:
            log_dir: Directory containing JSON log files
        """
        self.log_dir = Path(log_dir)
        self.metrics: Dict[str, Any] = {
            "missions": [],
            "llm_calls": [],
            "failures": [],
            "replans": [],
            "total_cost": 0.0,
            "total_tokens": 0,
            "total_duration": 0.0
        }

    def parse_log_files(self, pattern: str = "*.json") -> int:
        """
        Parse all JSON log files in log directory.

        Args:
            pattern: Glob pattern for log files (default: *.json)

        Returns:
            Number of log files processed
        """
        log_files = list(self.log_dir.glob(pattern))
        logger.info(f"Found {len(log_files)} log files to process")

        for log_file in log_files:
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            log_entry = json.loads(line.strip())
                            self._process_log_entry(log_entry)
                        except json.JSONDecodeError:
                            continue  # Skip malformed lines
            except Exception as e:
                logger.warning(f"Error processing {log_file}: {e}")

        return len(log_files)

    def _process_log_entry(self, entry: Dict[str, Any]) -> None:
        """Process a single log entry and extract metrics."""
        if not isinstance(entry, dict) or 'record' not in entry:
            return

        record = entry['record']
        message = record.get('message', '')

        # Extract event type if present in extra fields
        extra = record.get('extra', {})
        event_type = extra.get('event_type')

        if event_type == 'mission_event':
            self._process_mission_event(extra)
        elif event_type == 'llm_call':
            self._process_llm_call(extra)
        elif event_type == 'failure_event':
            self._process_failure_event(extra)

    def _process_mission_event(self, data: Dict[str, Any]) -> None:
        """Process mission lifecycle events."""
        event = data.get('event')
        status = data.get('status')

        if event == 'mission_end' and status == 'completed':
            self.metrics['missions'].append({
                'success': True,
                'duration': data.get('duration_seconds', 0),
                'attempts': data.get('attempts', 1),
                'timestamp': data.get('timestamp')
            })
        elif event == 'mission_end' and status == 'failed':
            self.metrics['missions'].append({
                'success': False,
                'duration': data.get('duration_seconds', 0),
                'attempts': data.get('attempts', 1),
                'failure_reason': data.get('failure_reason'),
                'timestamp': data.get('timestamp')
            })

    def _process_llm_call(self, data: Dict[str, Any]) -> None:
        """Process LLM call events."""
        tokens = data.get('tokens', {})
        duration_ms = data.get('duration_ms', 0)

        self.metrics['llm_calls'].append({
            'agent': data.get('agent'),
            'tokens': tokens,
            'duration_ms': duration_ms,
            'error': data.get('error'),
            'timestamp': data.get('timestamp')
        })

        # Aggregate totals
        if tokens:
            self.metrics['total_tokens'] += tokens.get('total', 0)

    def _process_failure_event(self, data: Dict[str, Any]) -> None:
        """Process failure and replan events."""
        self.metrics['failures'].append({
            'failure_type': data.get('failure_type'),
            'agent': data.get('agent'),
            'replan_triggered': data.get('replan_triggered', False),
            'timestamp': data.get('timestamp')
        })

        if data.get('replan_triggered'):
            self.metrics['replans'].append(data)

    def calculate_statistics(self) -> Dict[str, Any]:
        """
        Calculate aggregated statistics.

        Returns:
            Dictionary with performance metrics
        """
        missions = self.metrics['missions']
        llm_calls = self.metrics['llm_calls']
        failures = self.metrics['failures']

        # Mission statistics
        total_missions = len(missions)
        successful_missions = sum(1 for m in missions if m['success'])
        success_rate = (successful_missions / total_missions * 100) if total_missions > 0 else 0

        # Execution time statistics
        execution_times = [m['duration'] for m in missions if m['duration'] > 0]
        avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0

        # Replan statistics
        total_replans = len(self.metrics['replans'])
        avg_replans = total_replans / total_missions if total_missions > 0 else 0

        # LLM statistics
        total_llm_calls = len(llm_calls)
        successful_calls = sum(1 for call in llm_calls if not call.get('error'))
        llm_error_rate = ((total_llm_calls - successful_calls) / total_llm_calls * 100) if total_llm_calls > 0 else 0

        # Token statistics
        total_prompt_tokens = sum(call.get('tokens', {}).get('prompt', 0) for call in llm_calls)
        total_completion_tokens = sum(call.get('tokens', {}).get('completion', 0) for call in llm_calls)
        total_tokens = total_prompt_tokens + total_completion_tokens

        # Cost estimation (gpt-4o-mini pricing)
        prompt_cost = total_prompt_tokens * 0.00000015  # $0.150 per 1M tokens
        completion_cost = total_completion_tokens * 0.0000006  # $0.600 per 1M tokens
        total_cost = prompt_cost + completion_cost

        # Latency statistics
        latencies = [call.get('duration_ms', 0) for call in llm_calls if call.get('duration_ms', 0) > 0]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0

        stats = {
            'performance': {
                'total_missions': total_missions,
                'successful_missions': successful_missions,
                'failed_missions': total_missions - successful_missions,
                'success_rate': round(success_rate, 2),
                'avg_execution_time': round(avg_execution_time, 2),
                'total_replans': total_replans,
                'avg_replans_per_mission': round(avg_replans, 2)
            },
            'llm_usage': {
                'total_calls': total_llm_calls,
                'successful_calls': successful_calls,
                'failed_calls': total_llm_calls - successful_calls,
                'error_rate': round(llm_error_rate, 2),
                'avg_latency_ms': round(avg_latency, 2)
            },
            'token_usage': {
                'total_tokens': total_tokens,
                'prompt_tokens': total_prompt_tokens,
                'completion_tokens': total_completion_tokens,
                'tokens_per_mission': round(total_tokens / total_missions, 0) if total_missions > 0 else 0
            },
            'cost_analysis': {
                'total_cost_usd': round(total_cost, 6),
                'cost_per_mission': round(total_cost / total_missions, 6) if total_missions > 0 else 0,
                'prompt_cost_usd': round(prompt_cost, 6),
                'completion_cost_usd': round(completion_cost, 6)
            },
            'failure_analysis': {
                'total_failures': len(failures),
                'failure_types': self._count_failure_types(failures),
                'replan_success_rate': round((total_replans / len(failures) * 100) if failures else 0, 2)
            }
        }

        return stats

    def _count_failure_types(self, failures: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count failures by type."""
        failure_counts = {}
        for failure in failures:
            failure_type = failure.get('failure_type', 'unknown')
            failure_counts[failure_type] = failure_counts.get(failure_type, 0) + 1
        return failure_counts

    def generate_markdown_report(
        self,
        output_path: str = "docs/evaluation/benchmark_report.md",
        include_timestamp: bool = True
    ) -> None:
        """
        Generate Markdown benchmark report.

        Args:
            output_path: Output file path for the report
            include_timestamp: Include generation timestamp in report
        """
        stats = self.calculate_statistics()

        # Build report sections
        sections = []

        # Header
        sections.append("# Benchmark Report - LLM_robot_2\n")

        if include_timestamp:
            sections.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        sections.append("\n## Executive Summary\n")
        sections.append(f"- **Total Missions:** {stats['performance']['total_missions']}")
        sections.append(f"- **Success Rate:** {stats['performance']['success_rate']}%")
        sections.append(f"- **Average Execution Time:** {stats['performance']['avg_execution_time']}s")
        sections.append(f"- **Total LLM Calls:** {stats['llm_usage']['total_calls']}")
        sections.append(f"- **Total Cost:** ${stats['cost_analysis']['total_cost_usd']}")

        # Performance Metrics
        sections.append("\n## Performance Metrics\n")
        sections.append("| Metric | Value |")
        sections.append("|--------|-------|")
        for key, value in stats['performance'].items():
            formatted_key = key.replace('_', ' ').title()
            sections.append(f"| {formatted_key} | {value} |")

        # LLM Usage Statistics
        sections.append("\n## LLM Usage Statistics\n")
        sections.append("| Metric | Value |")
        sections.append("|--------|-------|")
        for key, value in stats['llm_usage'].items():
            formatted_key = key.replace('_', ' ').title()
            sections.append(f"| {formatted_key} | {value} |")

        # Token Usage
        sections.append("\n## Token Usage Analysis\n")
        sections.append("| Metric | Value |")
        sections.append("|--------|-------|")
        for key, value in stats['token_usage'].items():
            formatted_key = key.replace('_', ' ').title()
            sections.append(f"| {formatted_key} | {value} |")

        # Cost Analysis
        sections.append("\n## Cost Analysis\n")
        sections.append("| Metric | Value |")
        sections.append("|--------|-------|")
        for key, value in stats['cost_analysis'].items():
            formatted_key = key.replace('_', ' ').title()
            sections.append(f"| {formatted_key} | ${value} |")

        # Failure Analysis
        sections.append("\n## Failure Analysis\n")
        sections.append(f"**Total Failures:** {stats['failure_analysis']['total_failures']}\n")
        sections.append("### Failure Types\n")
        sections.append("| Failure Type | Count |")
        sections.append("|--------------|-------|")
        for failure_type, count in stats['failure_analysis']['failure_types'].items():
            sections.append(f"| {failure_type} | {count} |")

        # Write report
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(sections))

        logger.info(f"Benchmark report generated: {output_path}")

    @classmethod
    def generate_from_logs(
        cls,
        log_dir: str = "logs",
        output_path: str = "docs/evaluation/benchmark_report.md"
    ) -> Dict[str, Any]:
        """
        Convenience method to generate report from log directory.

        Args:
            log_dir: Directory containing JSON log files
            output_path: Output path for Markdown report

        Returns:
            Calculated statistics dictionary
        """
        report = cls(log_dir=log_dir)
        files_processed = report.parse_log_files()

        if files_processed == 0:
            logger.warning("No log files found. Report will be empty.")

        stats = report.calculate_statistics()
        report.generate_markdown_report(output_path=output_path)

        return stats
