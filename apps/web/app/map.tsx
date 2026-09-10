'use client';
import {useEffect,useRef} from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.markercluster';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import type {Entity,Geo} from '@/lib/client';
export default function MapView({rows,center,radius,onSelect,onBounds}:{rows:Entity[];center:Geo;radius:number|null;onSelect:(e:Entity)=>void;onBounds:(b:string)=>void}){
 const root=useRef<HTMLDivElement>(null),map=useRef<L.Map|null>(null),cluster=useRef<L.MarkerClusterGroup|null>(null),overlay=useRef<L.LayerGroup|null>(null);
 const boundsCallback=useRef(onBounds);boundsCallback.current=onBounds;
 useEffect(()=>{if(!root.current)return;const m=L.map(root.current).setView([center.latitude,center.longitude],12);map.current=m;L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap contributors',maxZoom:19}).addTo(m);cluster.current=L.markerClusterGroup({chunkedLoading:true}).addTo(m);overlay.current=L.layerGroup().addTo(m);let timer:ReturnType<typeof setTimeout>;const notify=()=>{clearTimeout(timer);timer=setTimeout(()=>{const b=m.getBounds();boundsCallback.current([b.getWest(),b.getSouth(),b.getEast(),b.getNorth()].join(','))},250)};m.on('moveend',notify);notify();return()=>{clearTimeout(timer);m.remove();map.current=null}},[]);
 useEffect(()=>{if(!map.current||!overlay.current)return;overlay.current.clearLayers();L.circleMarker([center.latitude,center.longitude],{radius:7,color:'#156e60',fillOpacity:1}).bindTooltip('Search center').addTo(overlay.current);if(radius)L.circle([center.latitude,center.longitude],{radius:radius*1000,color:'#247c6e',weight:1,fillOpacity:.05}).addTo(overlay.current);map.current.setView([center.latitude,center.longitude],radius&&radius>25?10:12)},[center.latitude,center.longitude,radius]);
 useEffect(()=>{const group=cluster.current;if(!group)return;group.clearLayers();for(const e of rows){if(e.latitude===null||e.longitude===null)continue;const box=document.createElement('div'),title=document.createElement('strong'),sub=document.createElement('p'),button=document.createElement('button');title.textContent=e.name;sub.textContent=[e.entity_type,e.distance_km!==null?e.distance_km+' km':null].filter(Boolean).join(' · ');button.textContent='View profile';button.style.color='#156e60';button.onclick=()=>onSelect(e);box.append(title,sub,button);L.marker([e.latitude,e.longitude],{icon:L.divIcon({className:'business-marker',html:'<span></span>',iconSize:[22,22],iconAnchor:[11,11]})}).bindPopup(box).addTo(group)}},[rows,onSelect]);
 return <div ref={root} className="map-surface" aria-label="Business locations map"/>;
}
