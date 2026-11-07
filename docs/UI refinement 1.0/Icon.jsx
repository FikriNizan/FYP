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
  brand: <><path d="M5 20V9m7 11V4m7 16v-7"/><path d="M3 20h18"/></>,
};
export default function Icon({name,className=''}) {
  return <svg className={'icon '+className} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] || paths.overview}</svg>;
}
