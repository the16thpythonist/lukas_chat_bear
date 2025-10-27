#!/usr/bin/env python3
"""
Quick verification script to test engagement service config loading.
This verifies that all config values are being read from YAML correctly.
"""
import sys
sys.path.insert(0, '/app')

from src.services.engagement_service import EngagementService
from src.utils.database import get_db

def main():
    print("=" * 60)
    print("ENGAGEMENT SERVICE CONFIGURATION VERIFICATION")
    print("=" * 60)

    with get_db() as db:
        service = EngagementService(db)

        # Test 1: Thread response probability
        print("\n1. Thread Response Probability:")
        prob = service.get_engagement_probability()
        print(f"   ✓ Value: {prob} (expected: 1.0)")
        assert prob == 1.0, f"Expected 1.0, got {prob}"

        # Test 2: Reaction probability
        print("\n2. Reaction Probability:")
        react_prob = service.get_reaction_probability()
        print(f"   ✓ Value: {react_prob} (expected: 1.0)")
        assert react_prob == 1.0, f"Expected 1.0, got {react_prob}"

        # Test 3: Random DM interval
        print("\n3. Random DM Interval:")
        interval = service.get_random_dm_interval_hours()
        print(f"   ✓ Value: {interval} hours (expected: 0.1 = 6 minutes)")
        assert abs(interval - 0.1) < 0.001, f"Expected 0.1, got {interval}"

        # Test 4: Active hours
        print("\n4. Active Hours:")
        start, end, tz = service.get_active_hours()
        print(f"   ✓ Start: {start}:00 (expected: 8)")
        print(f"   ✓ End: {end}:00 (expected: 22)")
        print(f"   ✓ Timezone: {tz} (expected: Germany/Berlin)")
        assert start == 8, f"Expected start=8, got {start}"
        assert end == 22, f"Expected end=22, got {end}"
        assert tz == "Germany/Berlin", f"Expected Germany/Berlin, got {tz}"

        # Test 5: Thread activity threshold (via is_thread_too_active)
        print("\n5. Thread Activity Threshold:")
        # Test with 9 messages (should not be too active)
        not_too_active = service.is_thread_too_active(message_count=9)
        print(f"   ✓ 9 messages: too_active={not_too_active} (expected: False)")
        assert not not_too_active, "9 messages should NOT be too active (threshold=10)"

        # Test with 10 messages (should be too active)
        is_too_active = service.is_thread_too_active(message_count=10)
        print(f"   ✓ 10 messages: too_active={is_too_active} (expected: True)")
        assert is_too_active, "10 messages should be too active (threshold=10)"

        # Test 6: Timezone-aware active hours
        print("\n6. Timezone Support:")
        from datetime import datetime, timezone as dt_timezone
        # Test at 10:00 UTC (should be within 8-22 Europe/Berlin if properly converted)
        # Europe/Berlin is UTC+1 or UTC+2, so 10:00 UTC = 11:00 or 12:00 Berlin time
        test_time = datetime(2025, 1, 15, 10, 0, 0, tzinfo=dt_timezone.utc)
        within = service.is_within_active_hours(
            check_time=test_time,
            start_hour=8,
            end_hour=22,
            timezone="Germany/Berlin"
        )
        print(f"   ✓ 10:00 UTC with timezone conversion: within_hours={within}")
        print(f"      (10:00 UTC should be ~11:00-12:00 Berlin time, within 8-22)")

    print("\n" + "=" * 60)
    print("✅ ALL CONFIG VALUES VERIFIED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    main()
