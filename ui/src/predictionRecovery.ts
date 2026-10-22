/** Only for read-only predictions from an already validated, immutable surrogate.
 * Never use this recovery loop for sampling, fitting, model runs or other writes. */
export async function recoverPrediction<T>(
  request: () => Promise<T>,
  transient: (error: unknown) => boolean,
  signal: AbortSignal,
): Promise<T> {
  for (let attempt = 0; ; attempt++) {
    signal.throwIfAborted();
    try {
      return await request();
    } catch (error) {
      signal.throwIfAborted();
      if (attempt === 2 || !transient(error)) throw error;
      await new Promise<void>((resolve, reject) => {
        const abort = () => {
          clearTimeout(timer);
          reject(signal.reason);
        };
        const timer = setTimeout(
          () => {
            signal.removeEventListener('abort', abort);
            resolve();
          },
          attempt === 0 ? 150 : 400,
        );
        signal.addEventListener('abort', abort, { once: true });
        if (signal.aborted) abort();
      });
    }
  }
}
