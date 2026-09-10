import type { Metadata } from 'next';
import './globals.css';
export const metadata:Metadata={title:'FieldAtlas — Business discovery',description:'Deterministic local business discovery with source provenance.'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>}