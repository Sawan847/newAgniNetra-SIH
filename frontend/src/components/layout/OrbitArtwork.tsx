/** Decorative orbital illustration; does not represent satellite measurements. */
export function OrbitArtwork() {
  return <div className="orbit-art" aria-hidden="true">
    <svg viewBox="0 0 440 300" fill="none">
      <defs>
        <radialGradient id="orbital-halo"><stop stopColor="#ffb47c" stopOpacity=".16"/><stop offset="1" stopColor="#ffb47c" stopOpacity="0"/></radialGradient>
        <radialGradient id="orbital-globe" cx=".25" cy=".25" r=".9"><stop stopColor="#40534b"/><stop offset=".48" stopColor="#202d2c"/><stop offset="1" stopColor="#10181c"/></radialGradient>
        <linearGradient id="orbital-edge" x1="130" y1="65" x2="290" y2="235" gradientUnits="userSpaceOnUse"><stop stopColor="#c7b798" stopOpacity=".65"/><stop offset="1" stopColor="#46616c" stopOpacity=".12"/></linearGradient>
        <clipPath id="orbital-clip"><circle cx="220" cy="150" r="82"/></clipPath>
      </defs>
      <circle cx="220" cy="150" r="145" fill="url(#orbital-halo)"/>
      <g stroke="#82938d" strokeOpacity=".14">
        <path d="M30 150h380M220 16v268" strokeDasharray="2 7"/>
        <circle cx="220" cy="150" r="123" strokeDasharray="1 7"/>
        <circle cx="220" cy="150" r="107"/>
        <ellipse cx="220" cy="150" rx="184" ry="51" transform="rotate(-27 220 150)"/>
        <ellipse cx="220" cy="150" rx="143" ry="111" transform="rotate(-27 220 150)"/>
      </g>
      <circle cx="220" cy="150" r="82" fill="url(#orbital-globe)" stroke="url(#orbital-edge)"/>
      <g clipPath="url(#orbital-clip)" stroke="#92b19e" strokeWidth=".7" strokeOpacity=".27">
        <ellipse cx="220" cy="150" rx="32" ry="82" transform="rotate(24 220 150)"/>
        <ellipse cx="220" cy="150" rx="61" ry="82" transform="rotate(24 220 150)"/>
        <ellipse cx="220" cy="150" rx="82" ry="29" transform="rotate(24 220 150)"/>
        <ellipse cx="220" cy="150" rx="82" ry="58" transform="rotate(24 220 150)"/>
        <path d="m170 94 10 8 19-6 15 12-8 14 10 11 14-6 17 7 4 16-15 5-3 22-12 8-6 26-10-7-4-18-15-8-5-18-15-4-8-20-14-12Z" fill="#95b895" fillOpacity=".055"/>
        <path d="m249 100 17 7 4 11 21 7-9 15-20-8-6 10-18-6 6-15-6-8Z"/>
      </g>
      <path d="M70 212c51 8 126-8 203-48 43-22 76-48 98-72" stroke="#deab79" strokeOpacity=".65" strokeWidth=".8"/>
      <g className="orbit-art__sweep"><circle cx="220" cy="43" r="4" fill="#f4c096"/><circle cx="220" cy="43" r="9" stroke="#f4c096" strokeOpacity=".25"/></g>
      <g className="orbit-art__beacon"><circle cx="242" cy="141" r="4" fill="#ffc18a"/><circle cx="242" cy="141" r="9" stroke="#ffc18a" strokeOpacity=".5"/><circle cx="242" cy="141" r="16" stroke="#ffc18a" strokeOpacity=".15"/></g>
      <path d="M254 140h49l18-23h46" stroke="#c6ad8d" strokeOpacity=".45" strokeWidth=".7"/>
      <text x="320" y="106" fill="#adac9c" fontSize="7" fontFamily="monospace" letterSpacing="1.3">THERMAL CONTEXT</text>
      <path d="m90 214 8-2m-4-3 2 8M366 53h8m-4-4v8" stroke="#9dbfb8" strokeWidth=".8"/>
      <text x="55" y="260" fill="#839690" fontSize="6" fontFamily="monospace" letterSpacing="1.4">OBSERVE / CONTEXTUALIZE / REVIEW</text>
    </svg>
  </div>;
}
