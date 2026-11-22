import React from 'react';

const paths = {
  overview: <><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><path d="M14 15h7m-7 5h7"/></>,
  cases: <><path d="M9 5H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-4"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="m8 13 3 3 5-6"/></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 11h18m-13 4h1m6 0h1m-8 3h1"/></>,
  guide: <><path d="M12 5C8 2 3 4 3 4v16s5-2 9 1c4-3 9-1 9-1V4s-5-2-9 1Zm0 0v16"/></>,
  research: <><path d="M4 4v16h17M8 15l4-5 4 2 5-7"/></>,
  wallet: <><path d="M4 7a2 2 0 0 1 2-2h12v4"/><path d="M4 7v10a2 2 0 0 0 2 2h14V9H6a2 2 0 0 1-2-2Z"/><circle cx="16.5" cy="14" r="1"/></>,
  deposit: <><path d="M3 10 12 4l9 6"/><path d="M5 10v8m4-8v8m6-8v8m4-8v8M3 20h18"/></>,
  receipt: <><path d="M6 3h12v18l-3-2-3 2-3-2-3 2Z"/><path d="M9 8h6m-6 4h6"/></>,
  waiver: <><path d="m19 5-14 14"/><circle cx="7" cy="7" r="2"/><circle cx="17" cy="17" r="2"/></>,
  lock: <><rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/></>,
  'payment-failed': <><path d="M3 8h15m-4-4 4 4-4 4M4 15l6 6m0-6-6 6"/></>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
  info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v5m0-9v.01"/></>,
  brand: <><path d="M5 20V9m7 11V4m7 16v-7"/><path d="M3 20h18"/></>,
  summary: <><path d="M5 4h14v16H5zM8 9h8M8 13h8M8 17h5"/></>,
  ops: <><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/></>,
  coin: <><circle cx="12" cy="12" r="9"/><path d="M14.8 9.2c-.6-.8-1.6-1.2-2.8-1.2-1.7 0-2.8.8-2.8 2s1 1.6 2.8 2 2.8.9 2.8 2.1-1.2 1.9-2.8 1.9c-1.3 0-2.3-.5-2.9-1.3M12 6.5V8M12 16v1.5"/></>,
  safe: <><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="12" cy="12" r="3.5"/><path d="M12 8.5V7M15.5 12H17"/></>,
  bank: <><path d="M3 10l9-6 9 6M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 21h18"/></>,
  yes: <><path d="M5 12.5l4.5 4.5L19 7.5"/></>,
  no: <><path d="M6 6l12 12M18 6L6 18"/></>,
  up: <><path d="M12 19V5M6 11l6-6 6 6"/></>,
  down: <><path d="M12 5v14M6 13l6 6 6-6"/></>,
  users: <><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.5 3.4-5.5 6.5-5.5s5.7 2 6.5 5.5M16 4.5a3.5 3.5 0 0 1 0 7M18.5 14.8c1.6.8 2.7 2.6 3 5.2"/></>,
  left: <><path d="M15 6l-6 6 6 6"/></>,
  screen: <><rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/></>,
  minus: <><path d="M5 12h14"/></>,
  search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
  message: <><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></>,
  flag: <><path d="M5 21V4h11l-2 4 2 4H5"/></>,
  grid: <><rect x="3" y="3" width="8" height="8" rx="1"/><rect x="13" y="3" width="8" height="8" rx="1"/><rect x="3" y="13" width="8" height="8" rx="1"/><rect x="13" y="13" width="8" height="8" rx="1"/></>,
};
export default function Icon({name,className=''}) {
  return <svg className={'icon '+className} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] || paths.overview}</svg>;
}
