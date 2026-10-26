import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.57.0'
const cors={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'authorization, x-client-info, apikey, content-type','Access-Control-Allow-Methods':'POST, OPTIONS'}
const json=(body:unknown,status=200)=>new Response(JSON.stringify(body),{status,headers:{...cors,'Content-Type':'application/json'}})
const url=Deno.env.get('SUPABASE_URL')!,key=Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
const admin=createClient(url,key,{auth:{autoRefreshToken:false,persistSession:false}})
const norm=(v:unknown)=>String(v??'').trim().toLowerCase()
const emailFor=(u:string)=>`${u.replace(/[^a-z0-9._-]/g,'-')}@username.ssc-smart-study.local`
Deno.serve(async req=>{
 if(req.method==='OPTIONS')return new Response('ok',{headers:cors})
 if(req.method!=='POST')return json({error:'POST required'},405)
 try{
  const {action,username,pin,display_name}=await req.json();const u=norm(username),p=String(pin??'')
  if(!/^[a-z0-9._-]{3,24}$/.test(u))return json({error:'Username must be 3–24 characters.'},400)
  if(!/^\d{6}$/.test(p))return json({error:'PIN must be exactly 6 digits.'},400)
  if(action!=='signup')return json({error:'Unknown action'},400)
  const {data:existing}=await admin.from('profiles').select('id').eq('username',u).maybeSingle()
  if(existing)return json({error:'Username already exists.'},409)
  const email=emailFor(u)
  const {data,error}=await admin.auth.admin.createUser({email,password:p,email_confirm:true,user_metadata:{username:u,display_name:String(display_name??u).trim().slice(0,60)||u}})
  if(error)return json({error:error.message},400)
  const user=data.user
  const {error:profileError}=await admin.from('profiles').insert({id:user.id,username:u,display_name:String(display_name??u).trim().slice(0,60)||u})
  if(profileError){await admin.auth.admin.deleteUser(user.id);return json({error:profileError.message},400)}
  return json({ok:true,username:u})
 }catch(e){return json({error:e instanceof Error?e.message:'Server error'},500)}
})
