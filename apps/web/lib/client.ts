export type Geo={provider_id:string;display_name:string;city?:string|null;district?:string|null;state?:string|null;country?:string|null;latitude:number;longitude:number;bounding_box:number[]|null};
export type Entity={id:string;name:string;entity_type:string|null;facility_type:string|null;category:string|null;specialties:string[];subspecialties:string[];services:string[];city:string|null;address:string|null;latitude:number|null;longitude:number|null;distance_km:number|null;rating:number|null;review_count:number|null;phone:string|null;email:string|null;whatsapp:string|null;website:string|null;source_count:number;completeness_score:number;confidence_score:number;confidence:string;is_demo:boolean;last_verified_at:string|null;possible_duplicate?:boolean;evidence?:any[];sources?:any[]};
export const initialBase=process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV==='development'?'http://127.0.0.1:8000':'');
export function validBase(input:string){const u=new URL(input);if(u.username||u.password||u.search||u.hash||!['https:','http:'].includes(u.protocol))throw Error('Use an HTTP(S) API origin.');if(u.protocol==='http:'&&!['localhost','127.0.0.1','[::1]'].includes(u.hostname))throw Error('Remote APIs must use HTTPS.');return input.replace(/\/$/,'');}
export async function callApi(base:string,key:string,path:string,init:RequestInit={}){
 if(!base)throw Error('Connect a running API to start discovery and create exports.');
 const response=await fetch(validBase(base)+path,{...init,headers:{'Content-Type':'application/json',...(key?{'X-API-Key':key}:{}),...init.headers},signal:AbortSignal.timeout(30000)});
 if(!response.ok){let d:any;try{d=await response.json()}catch{d={detail:response.statusText}}throw Error(typeof d.detail==='string'?d.detail:JSON.stringify(d.detail));}
 return response.json();
}
