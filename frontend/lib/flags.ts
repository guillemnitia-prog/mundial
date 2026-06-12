// Código FIFA (TLA, 3 letras) → ISO 3166-1 alpha-2, para la bandera emoji.
const TLA_TO_ISO2: Record<string, string> = {
  ALG: "DZ", ARG: "AR", AUS: "AU", AUT: "AT", BEL: "BE", BIH: "BA", BRA: "BR",
  CAN: "CA", CPV: "CV", COL: "CO", COD: "CD", CRO: "HR", CUW: "CW", CZE: "CZ",
  ECU: "EC", EGY: "EG", FRA: "FR", GER: "DE", GHA: "GH", HAI: "HT", IRN: "IR",
  IRQ: "IQ", CIV: "CI", JPN: "JP", JOR: "JO", MEX: "MX", MAR: "MA", NED: "NL",
  NZL: "NZ", NOR: "NO", PAN: "PA", PAR: "PY", POR: "PT", QAT: "QA", KSA: "SA",
  SEN: "SN", RSA: "ZA", KOR: "KR", ESP: "ES", SWE: "SE", SUI: "CH", TUN: "TN",
  TUR: "TR", USA: "US", URY: "UY", UZB: "UZ",
};

// Banderas de subdivisiones del Reino Unido (no son ISO alpha-2).
const SPECIAL: Record<string, string> = {
  ENG: "\u{1F3F4}\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}", // England
  SCO: "\u{1F3F4}\u{E0067}\u{E0062}\u{E0073}\u{E0063}\u{E0074}\u{E007F}", // Scotland
  WAL: "\u{1F3F4}\u{E0067}\u{E0062}\u{E0077}\u{E006C}\u{E0073}\u{E007F}", // Wales
};

export function flag(tla: string | null | undefined): string {
  if (!tla) return "";
  const up = tla.toUpperCase();
  if (SPECIAL[up]) return SPECIAL[up];
  const iso = TLA_TO_ISO2[up];
  if (!iso) return "";
  // Letras → indicadores regionales.
  return iso.replace(/./g, (c) => String.fromCodePoint(0x1f1e6 + c.charCodeAt(0) - 65));
}
