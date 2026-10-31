// Every end of a turn, to Weft, whatever ended it: the person's interrupt
// sends no classic hook, so without this a pane would read as still working.
import type { Register } from 'claude-code';

export const register: Register = (on) => {
  on('turn.complete', async ($, e, next) => {
    const ended = await next(e);
    // A subagent's turn is not the pane's.
    if (e.agentId === undefined) {
      const said = JSON.stringify({
        session_id: await $.session.id(),
        cwd: await $.session.cwd(),
        reason: e.reason,
      });
      const signal = [`${$.plugin.root}/hooks/weft-signal`, 'claude-code', 'TurnComplete'];
      void $.process.run(signal, { stdin: said, timeoutMs: 10_000 }).catch(() => undefined);
    }
    return ended;
  });
};
