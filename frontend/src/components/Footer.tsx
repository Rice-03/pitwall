export function Footer() {
  return (
    <footer className="border-t border-slate-800 px-4 py-3 text-center text-xs text-slate-500">
      Pit Wall is a portfolio project: an LLM front end over{" "}
      <a
        href="https://docs.fastf1.dev/"
        target="_blank"
        rel="noreferrer"
        className="underline decoration-slate-600 hover:text-slate-300"
      >
        FastF1
      </a>{" "}
      race data, not a race simulator or strategy optimiser. Tyre degradation figures are
      approximate: the fuel-burn correction assumes a fixed seconds-per-lap constant, since fuel
      load and tyre age can&apos;t be separated within a single stint.
    </footer>
  );
}
