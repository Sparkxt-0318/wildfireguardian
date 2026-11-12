"""DIAGNOSTIC launcher (kit v2 Step 3, locate overruns): runs the worker named by WFG_PHASE_TARGET via runpy and samples
the main thread's stack every 0.5 s from a daemon thread. Writes STACK_SAMPLES.json (counts per innermost-5-frame key,
with the time of first and last sample) in the job folder at exit. Changes nothing the worker computes."""
import atexit, collections, json, os, pathlib, runpy, sys, threading, time
target = os.environ['WFG_PHASE_TARGET']
main_id = threading.get_ident(); t0 = time.perf_counter()
counts = collections.Counter(); first = {}; last = {}; stop = [False]
def key(fr):
    out = []
    while fr is not None and len(out) < 6:
        out.append('%s:%s:%d' % (os.path.basename(fr.f_code.co_filename), fr.f_code.co_name, fr.f_lineno)); fr = fr.f_back
    return ' < '.join(out)
def run():
    while not stop[0]:
        fr = sys._current_frames().get(main_id)
        if fr is not None:
            k = key(fr); t = round(time.perf_counter() - t0, 1)
            counts[k] += 1; first.setdefault(k, t); last[k] = t
        time.sleep(0.5)
        if int(time.perf_counter() - t0) % 10 == 0:
            try:
                dump(final=False)
            except Exception:
                pass
def dump(final=True):
    if final:
        stop[0] = True
    try:
        job = json.loads(pathlib.Path(sys.argv[sys.argv.index('--job-file') + 1]).read_text()) if '--job-file' in sys.argv else None
    except Exception:
        job = None
    folder = pathlib.Path(job['output_path']) if job else pathlib.Path('.')
    rows = sorted(({'key': k, 'samples': n, 'first_s': first[k], 'last_s': last[k]} for k, n in counts.items()), key=lambda r: -r['samples'])
    (folder / 'STACK_SAMPLES.json').write_text(json.dumps(rows[:200], indent=1))
atexit.register(dump)
threading.Thread(target=run, daemon=True).start()
sys.argv[0] = target
runpy.run_path(target, run_name='__main__')
