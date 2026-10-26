import { createClient } from "npm:@supabase/supabase-js@2.57.0";
const URL = Deno.env.get("SUPABASE_URL") ?? "";
const ANON = Deno.env.get("SUPABASE_ANON_KEY") ?? Deno.env.get("SUPABASE_PUBLISHABLE_KEY") ?? "";
const SERVICE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const ORIGINS = new Set(["https://mondaljeet126580-bit.github.io","http://localhost:5500","http://127.0.0.1:5500","http://localhost:3000","null"]);
const clean=(v:unknown,n=240)=>typeof v==="string"?v.trim().slice(0,n):"";
const unique=(v:unknown[])=>Array.from(new Set(v.filter((x):x is string=>typeof x==="string"&&x.length>0)));
function cors(origin:string|null){const h:Record<string,string>={"Access-Control-Allow-Headers":"authorization, apikey, content-type, x-client-info","Access-Control-Allow-Methods":"POST, OPTIONS","Access-Control-Max-Age":"86400","Vary":"Origin"};if(origin&&ORIGINS.has(origin))h["Access-Control-Allow-Origin"]=origin;return h}
function out(data:unknown,status=200,origin:string|null=null){return new Response(JSON.stringify(data),{status,headers:{...cors(origin),"Content-Type":"application/json; charset=utf-8","Cache-Control":"no-store"}})}
Deno.serve(async(req:Request)=>{
 const origin=req.headers.get("origin");
 if(req.method==="OPTIONS")return new Response("ok",{headers:cors(origin)});
 if(req.method!=="POST")return out({error:"শুধু POST request গ্রহণ করা হয়।"},405,origin);
 if(!URL||!ANON||!SERVICE)return out({error:"Edge Function environment অসম্পূর্ণ।"},500,origin);
 try{
  const header=req.headers.get("Authorization")??"",jwt=header.startsWith("Bearer ")?header.slice(7):"";
  if(!jwt)return out({error:"Google দিয়ে লগইন করো।"},401,origin);
  const authClient=createClient(URL,ANON,{auth:{persistSession:false,autoRefreshToken:false}});
  const {data:authData,error:authError}=await authClient.auth.getUser(jwt),caller=authData?.user;
  if(authError||!caller)return out({error:"লগইন সেশন বৈধ নয়। আবার লগইন করো।"},401,origin);
  if(!caller.email||!caller.email_confirmed_at)return out({error:"ভেরিফাই করা Google/Gmail account দরকার।"},403,origin);
  const admin=createClient(URL,SERVICE,{auth:{persistSession:false,autoRefreshToken:false}}),email=caller.email.toLowerCase().trim();
  const {data:account,error:accountError}=await admin.from("admin_accounts").select("id,username,display_name,enabled").eq("id",caller.id).eq("enabled",true).maybeSingle();
  if(accountError)throw accountError;
  if(!account)return out({error:"এই অ্যাকাউন্টটি Admin হিসেবে অনুমোদিত নয়।",code:"ADMIN_NOT_ALLOWLISTED"},403,origin);
  const {data:allow,error:allowError}=await admin.from("admin_allowlist").select("email").eq("email",email).eq("enabled",true).maybeSingle();
  if(allowError)throw allowError;
  if(!allow)return out({error:"এই Admin account-এর অনুমতি নেই।",code:"ADMIN_NOT_ALLOWLISTED"},403,origin);
  const input=await req.json().catch(()=>({})),action=clean(input.action,50);
  async function audit(actionName:string,targetId:string|null=null,details:Record<string,unknown>={}){const {error}=await admin.from("admin_audit_logs").insert({admin_user_id:caller.id,admin_email:email,action:actionName,target_user_id:targetId,details});if(error)throw error}
  async function authInfo(id:string){const {data,error}=await admin.auth.admin.getUserById(id);if(error)return null;const u=data.user;return u?{id:u.id,email:u.email??null,email_confirmed_at:u.email_confirmed_at??null,created_at:u.created_at??null,last_sign_in_at:u.last_sign_in_at??null,is_anonymous:Boolean((u as any).is_anonymous),providers:(u.identities??[]).map((x:any)=>x.provider).filter(Boolean)}:null}
  async function countRows(table:string,filter?:(q:any)=>any){let q=admin.from(table).select("*",{count:"exact",head:true});if(filter)q=filter(q);const {count,error}=await q;if(error)throw error;return count??0}

  if(action==="maintenance_change"){
   const enabled=Boolean(input.enabled);
   const message=clean(input.message,500)||"on maintenance";
   const {data:state,error}=await admin.rpc("admin_set_maintenance",{p_enabled:enabled,p_message:message});
   if(error)throw error;
   await audit("maintenance_change",null,{enabled:state.enabled,message:state.message});
   return out({ok:true,maintenance:state},200,origin);
  }
  if(action==="dashboard"){
   await audit("view_dashboard");
   const [users,online,banned,messages,conversations,recent]=await Promise.all([
    countRows("profiles"),countRows("profiles",(q:any)=>q.eq("is_online",true)),countRows("profiles",(q:any)=>q.eq("is_banned",true)),countRows("messages"),countRows("conversations"),
    admin.from("messages").select("id,conversation_id,sender_id,body,created_at,read_at,delivered_at,deleted_at,delete_for_everyone").order("created_at",{ascending:false}).limit(12)
   ]);
   if(recent.error)throw recent.error;
   const ids=unique((recent.data??[]).map((m:any)=>m.sender_id));
   const {data:profiles,error}=ids.length?await admin.from("profiles").select("id,username,display_name").in("id",ids):{data:[],error:null};
   if(error)throw error;const map=new Map((profiles??[]).map((p:any)=>[p.id,p]));
   const recentMessages=(recent.data??[]).map((m:any)=>({...m,sender_name:(map.get(m.sender_id) as any)?.display_name||(map.get(m.sender_id) as any)?.username||"Unknown user"}));
   return out({ok:true,stats:{users,online,banned,messages,conversations},recentMessages,admin:{email,username:account.username,display_name:account.display_name}},200,origin);
  }
  if(action==="users"){
   const search=clean(input.search,100).replace(/[,%()]/g," "),page=Math.max(1,Math.min(5000,Number(input.page)||1)),perPage=Math.max(10,Math.min(50,Number(input.perPage)||25));
   let q=admin.from("profiles").select("id,username,display_name,created_at,last_seen,is_online,is_banned,ban_reason,banned_at",{count:"exact"}).order("created_at",{ascending:false}).range((page-1)*perPage,page*perPage-1);
   if(search)q=q.or("username.ilike.%"+search+"%,display_name.ilike.%"+search+"%");
   const {data,error,count}=await q;if(error)throw error;
   const users=await Promise.all((data??[]).map(async(p:any)=>({...p,auth:await authInfo(p.id)})));
   await audit("list_users",null,{search,page,returned:users.length});
   return out({ok:true,users,total:count??0,page,perPage},200,origin);
  }
  if(action==="user_detail"){
   const target=clean(input.userId,80);if(!target)return out({error:"User ID লাগবে।"},400,origin);
   const [pr,au,mem]=await Promise.all([
    admin.from("profiles").select("id,username,display_name,avatar_url,created_at,updated_at,last_seen,is_online,is_banned,ban_reason,banned_at,banned_by").eq("id",target).maybeSingle(),
    authInfo(target),
    admin.from("conversation_members").select("conversation_id,user_id,joined_at,last_read_at").eq("user_id",target)
   ]);
   if(pr.error)throw pr.error;if(mem.error)throw mem.error;if(!pr.data&&!au)return out({error:"User পাওয়া যায়নি।"},404,origin);
   const cids=unique((mem.data??[]).map((x:any)=>x.conversation_id));let convs:any[]=[],members:any[]=[],msgs:any[]=[];
   if(cids.length){
    const [c,m,msg]=await Promise.all([
     admin.from("conversations").select("id,created_by,is_group,is_direct,title,created_at").in("id",cids).order("created_at",{ascending:false}),
     admin.from("conversation_members").select("conversation_id,user_id,joined_at,last_read_at").in("conversation_id",cids),
     admin.from("messages").select("id,conversation_id,sender_id,body,created_at,edited_at,deleted_at,deleted_by,delete_for_everyone,delivered_at,read_at,image_path,image_name,image_mime_type,image_size").in("conversation_id",cids).order("created_at",{ascending:false}).limit(2000)
    ]);
    if(c.error)throw c.error;if(m.error)throw m.error;if(msg.error)throw msg.error;convs=c.data??[];members=m.data??[];msgs=msg.data??[];
   }
   const ids=unique([...members.map((x:any)=>x.user_id),...msgs.map((x:any)=>x.sender_id)]);
   const {data:related,error:re}=ids.length?await admin.from("profiles").select("id,username,display_name,is_online,is_banned").in("id",ids):{data:[],error:null};
   if(re)throw re;const pmap=new Map((related??[]).map((p:any)=>[p.id,p]));
   const mapped=convs.map((c:any)=>({...c,participants:members.filter((m:any)=>m.conversation_id===c.id).map((m:any)=>{const p:any=pmap.get(m.user_id)||{};return{user_id:m.user_id,username:p.username??null,display_name:p.display_name??"Unknown user",is_online:p.is_online??false,is_banned:p.is_banned??false,last_read_at:m.last_read_at}})}));
   const paths=unique(msgs.filter((m:any)=>m.image_path&&!m.deleted_at&&!m.delete_for_everyone).map((m:any)=>m.image_path));
   if(paths.length){try{const {data:signed,error}=await admin.storage.from("chat-images").createSignedUrls(paths,300);if(!error&&signed){const smap=new Map(signed.map((x:any,i:number)=>[x.path||paths[i],x.signedUrl]));msgs=msgs.map((m:any)=>({...m,image_url:m.image_path?(smap.get(m.image_path)??null):null}))}}catch(e){console.warn("image signing",e)}}
   const me=(mem.data??[]).find((m:any)=>m.user_id===target);
   await audit("view_user_detail",target,{conversation_count:convs.length,messages_returned:msgs.length});
   return out({ok:true,user:{...(pr.data??{id:target}),auth:au,last_read_at:me?.last_read_at??null},conversations:mapped,messages:msgs,messageLimit:2000},200,origin);
  }
  if(action==="ban_user"||action==="unban_user"){
   const target=clean(input.userId,80);if(!target)return out({error:"User ID লাগবে।"},400,origin);if(target===caller.id)return out({error:"নিজের Admin account ব্যান করা যাবে না।"},400,origin);
   const banned=action==="ban_user";
   const {data:p,error}=await admin.from("profiles").update({is_banned:banned,ban_reason:banned?(clean(input.reason,500)||"Admin decision"):null,banned_at:banned?new Date().toISOString():null,banned_by:banned?caller.id:null}).eq("id",target).select("id,is_banned,ban_reason,banned_at").maybeSingle();
   if(error)throw error;if(!p)return out({error:"User profile পাওয়া যায়নি।"},404,origin);
   const {error:authError}=await admin.auth.admin.updateUserById(target,{ban_duration:banned?"876000h":"none"});if(authError)throw authError;
   await audit(action,target,{reason:banned?p.ban_reason:null});return out({ok:true,user:p},200,origin);
  }
  if(action==="audit_logs"){
   const {data,error}=await admin.from("admin_audit_logs").select("id,admin_user_id,admin_email,action,target_user_id,details,created_at").order("created_at",{ascending:false}).limit(150);
   if(error)throw error;await audit("view_audit_logs",null,{returned:(data??[]).length});return out({ok:true,logs:data??[]},200,origin);
  }
  if(action==="delete_message"){
   const id=clean(input.messageId,80);if(!id)return out({error:"Message ID লাগবে।"},400,origin);
   const {data:m,error}=await admin.from("messages").select("id,conversation_id,sender_id,image_path").eq("id",id).maybeSingle();if(error)throw error;if(!m)return out({error:"মেসেজ পাওয়া যায়নি।"},404,origin);
   if(m.image_path){const {error:se}=await admin.storage.from("chat-images").remove([m.image_path]);if(se)console.warn(se.message)}
   const {error:de}=await admin.from("messages").delete().eq("id",id);if(de)throw de;await audit("delete_message",m.sender_id,{message_id:id,conversation_id:m.conversation_id});return out({ok:true},200,origin);
  }
  if(action==="delete_user"){
   const target=clean(input.userId,80);if(!target)return out({error:"User ID লাগবে।"},400,origin);if(target===caller.id)return out({error:"নিজের Admin account মুছে ফেলা যাবে না।"},400,origin);
   if(!await authInfo(target))return out({error:"Auth account পাওয়া যায়নি।"},404,origin);
   await audit("delete_user_started",target,{warning:"All conversations and messages in those conversations are permanently removed."});
   await admin.auth.admin.updateUserById(target,{ban_duration:"876000h"});
   const [mr,cr,own]=await Promise.all([
    admin.from("conversation_members").select("conversation_id").eq("user_id",target),
    admin.from("conversations").select("id").eq("created_by",target),
    admin.from("messages").select("image_path").eq("sender_id",target)
   ]);
   if(mr.error)throw mr.error;if(cr.error)throw cr.error;if(own.error)throw own.error;
   const cids=unique([...(mr.data??[]).map((x:any)=>x.conversation_id),...(cr.data??[]).map((x:any)=>x.id)]);
   let paths=unique((own.data??[]).map((x:any)=>x.image_path));
   if(cids.length){const {data:all,error}=await admin.from("messages").select("image_path").in("conversation_id",cids);if(error)throw error;paths=unique([...paths,...(all??[]).map((x:any)=>x.image_path)])}
   for(let i=0;i<paths.length;i+=100){const {error}=await admin.storage.from("chat-images").remove(paths.slice(i,i+100));if(error)console.warn("image cleanup",error.message)}
   if(cids.length){
    const {error:e1}=await admin.from("messages").delete().in("conversation_id",cids);if(e1)throw e1;
    const {error:e2}=await admin.from("conversation_members").delete().in("conversation_id",cids);if(e2)throw e2;
    const {error:e3}=await admin.from("conversations").delete().in("id",cids);if(e3)throw e3;
   }
   const {error:e4}=await admin.from("messages").update({deleted_by:null}).eq("deleted_by",target);if(e4)throw e4;
   const {error:e5}=await admin.from("messages").delete().eq("sender_id",target);if(e5)throw e5;
   const {error:e6}=await admin.from("profiles").delete().eq("id",target);if(e6)throw e6;
   const {error:e7}=await admin.auth.admin.deleteUser(target);if(e7)throw e7;
   await audit("delete_user_completed",target,{deleted_conversations:cids.length});return out({ok:true,deleted_conversations:cids.length},200,origin);
  }
  return out({error:"অজানা admin action।"},400,origin);
 }catch(e){console.error("admin-console",e);return out({error:e instanceof Error?e.message:"Server error"},500,origin)}
});