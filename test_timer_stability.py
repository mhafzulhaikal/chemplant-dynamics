import statistics
import time

from engine.appdb import AppDB
from gateway.bridge import Bridge


def test_stability():
    appdb = AppDB()
    bridge = Bridge(appdb=appdb, case_name='sthr')

    # Configure for real-time
    bridge.state.acceleration = 1.0
    bridge.state.time_end = 'Infinity'
    bridge.apply_runtime_configuration(restart_if_needed=False)

    print('Starting simulation...')
    bridge.start()

    # Wait for the engine to spin up and produce the first tick
    while bridge.state.global_sim_time <= 0:
        time.sleep(0.01)

    print(f'Engine running. Initial sim_time: {bridge.state.global_sim_time:.4f} min')

    start_wall = time.perf_counter()
    start_sim_min = bridge.state.global_sim_time

    errors = []
    wall_deltas = []
    sim_deltas = []

    last_wall = start_wall
    last_sim = start_sim_min

    test_duration = 10.0
    poll_interval = 0.01  # Poll very fast to catch the exact moment it changes

    print(f'Sampling for {test_duration} seconds (recording only on sim_time changes)...')

    while True:
        now_wall = time.perf_counter()
        elapsed_wall = now_wall - start_wall

        if elapsed_wall >= test_duration:
            break

        now_sim_min = bridge.state.global_sim_time

        # Only record when the simulation time actually ticks forward
        if now_sim_min > last_sim:
            # Calculate instantaneous deltas
            dt_wall = now_wall - last_wall
            dt_sim_min = now_sim_min - last_sim
            dt_sim_sec = dt_sim_min * 60.0

            wall_deltas.append(dt_wall)
            sim_deltas.append(dt_sim_sec)

            # We expect dt_sim_sec to equal dt_wall (in a perfect real-time simulation)
            error = dt_sim_sec - dt_wall
            errors.append(error)

            last_wall = now_wall
            last_sim = now_sim_min

        # Sleep until next poll
        time.sleep(poll_interval)

    bridge.stop()

    print('\n--- Stability Test Results ---')
    print(f'Physics Steps caught: {len(errors)}')

    if len(errors) == 0:
        print('No steps recorded!')
        return

    mean_error = statistics.mean(errors)
    mean_abs_error = statistics.mean([abs(e) for e in errors])
    max_error = max(errors)
    min_error = min(errors)

    print(f'Mean error (sim_dt - wall_dt): {mean_error * 1000:.2f} ms')
    print(f'Mean absolute error:           {mean_abs_error * 1000:.2f} ms')
    print(f'Max error peak:                {max_error * 1000:.2f} ms')
    print(f'Min error peak:                {min_error * 1000:.2f} ms')

    # Calculate jitter (standard deviation of the error)
    if len(errors) >= 2:
        std_dev = statistics.stdev(errors)
        print(f'Error Standard Deviation:      {std_dev * 1000:.2f} ms (Jitter)')
    else:
        print('Not enough samples for standard deviation.')

    # Calculate overall drift
    total_wall_elapsed = last_wall - start_wall
    total_sim_elapsed = (last_sim - start_sim_min) * 60.0
    drift = total_sim_elapsed - total_wall_elapsed
    print(f'\nTotal Wall Time Elapsed:       {total_wall_elapsed:.4f} s')
    print(f'Total Sim Time Elapsed:        {total_sim_elapsed:.4f} s')
    print(f'Cumulative Drift:              {drift * 1000:.2f} ms')


if __name__ == '__main__':
    test_stability()
