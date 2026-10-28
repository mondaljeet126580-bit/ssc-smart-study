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

  if(action==="automation_status"){
   const {data:setting,error:settingError}=await admin.from("app_settings").select("value").eq("key","chatlink_automation").maybeSingle();
   if(settingError)throw settingError;
   const raw=setting?.value&&typeof setting.value==="object"?setting.value:{};
   const automation={enabled:raw.enabled===true};
   return out({ok:true,automation},200,origin);
  }
  if(action==="automation_change"){
   if(typeof input.enabled!=="boolean")return out({error:"Automation ON/OFF-এর জন্য valid enabled value লাগবে।"},400,origin);
   const automation={enabled:input.enabled};
   const {error:saveError}=await admin.from("app_settings").upsert({
    key:"chatlink_automation",
    value:automation,
    updated_at:new Date().toISOString()
   },{onConflict:"key"});
   if(saveError)return out({error:saveError.message||"Automation setting save failed."},500,origin);
   try{await audit("automation_change",null,{enabled:automation.enabled})}
   catch(auditError){console.error("automation audit log failed",auditError)}
   return out({ok:true,automation},200,origin);
  }
  if(action==="maintenance_change"){
   const enabled=input.enabled===true;
   const message=clean(input.message,500)||"on maintenance";
   const state={enabled,message};
   // Auth session, admin_accounts, and admin_allowlist were verified above.
   const {error:saveError}=await admin.from("app_settings").upsert({
    key:"maintenance",
    value:state,
    updated_at:new Date().toISOString()
   },{onConflict:"key"});
   if(saveError)return out({error:saveError.message||"Maintenance setting save failed."},500,origin);
   try{await audit("maintenance_change",null,{enabled:state.enabled,message:state.message})}
   catch(auditError){console.error("maintenance audit log failed",auditError)}
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
   let q=admin.from("profiles").select("id,username,display_name,avatar_url,about,created_at,last_seen,is_online,is_banned,ban_reason,banned_at",{count:"exact"}).order("created_at",{ascending:false}).range((page-1)*perPage,page*perPage-1);
   if(search)q=q.or("username.ilike.%"+search+"%,display_name.ilike.%"+search+"%");
   const {data,error,count}=await q;if(error)throw error;
   const users=await Promise.all((data??[]).map(async(p:any)=>({...p,auth:await authInfo(p.id)})));
   await audit("list_users",null,{search,page,returned:users.length});
   return out({ok:true,users,total:count??0,page,perPage},200,origin);
  }
  if(action==="user_detail"){
   const target=clean(input.userId,80);if(!target)return out({error:"User ID লাগবে।"},400,origin);
   const [pr,au,mem]=await Promise.all([
    admin.from("profiles").select("id,username,display_name,avatar_url,about,created_at,updated_at,last_seen,is_online,is_banned,ban_reason,banned_at,banned_by").eq("id",target).maybeSingle(),
    authInfo(target),
    admin.from("conversation_members").select("conversation_id,user_id,joined_at,last_read_at").eq("user_id",target)
   ]);
   if(pr.error)throw pr.error;if(mem.error)throw mem.error;if(!pr.data&&!au)return out({error:"User পাওয়া যায়নি।"},404,origin);
   const cids=unique((mem.data??[]).map((x:any)=>x.conversation_id));let convs:any[]=[],members:any[]=[];
   if(cids.length){
    const [c,m]=await Promise.all([
     admin.from("conversations").select("id,created_by,is_group,is_direct,title,created_at").in("id",cids).order("created_at",{ascending:false}),
     admin.from("conversation_members").select("conversation_id,user_id,joined_at,last_read_at").in("conversation_id",cids)
    ]);
    if(c.error)throw c.error;if(m.error)throw m.error;convs=c.data??[];members=m.data??[];
   }
   const ids=unique(members.map((x:any)=>x.user_id));
   const {data:related,error:re}=ids.length?await admin.from("profiles").select("id,username,display_name,avatar_url,about,is_online,is_banned,last_seen,created_at").in("id",ids):{data:[],error:null};
   if(re)throw re;const pmap=new Map((related??[]).map((p:any)=>[p.id,p]));
   const mapped=await Promise.all(convs.map(async(c:any)=>{
    const [messageCount,lastMessage,reportRows]=await Promise.all([
     countRows("messages",(q:any)=>q.eq("conversation_id",c.id)),
     admin.from("messages").select("created_at,sender_id").eq("conversation_id",c.id).order("created_at",{ascending:false}).limit(1),
     admin.from("message_reports").select("id,status,reason,created_at,reported_by").eq("conversation_id",c.id).order("created_at",{ascending:false}).limit(20)
    ]);
    if(lastMessage.error)throw lastMessage.error;if(reportRows.error)throw reportRows.error;
    const participants=members.filter((m:any)=>m.conversation_id===c.id).map((m:any)=>{
     const p:any=pmap.get(m.user_id)||{};
     return{user_id:m.user_id,username:p.username??null,display_name:p.display_name??"Unknown user",avatar_url:p.avatar_url??null,about:p.about??"",is_online:p.is_online??false,is_banned:p.is_banned??false,last_seen:p.last_seen??null,created_at:p.created_at??null,last_read_at:m.last_read_at??null};
    });
    const reports=(reportRows.data??[]).map((r:any)=>({...r,active:r.status==="pending"||r.status==="in_review"}));
    return{...c,participants,message_count:messageCount,last_message_at:lastMessage.data?.[0]?.created_at??null,last_sender_id:lastMessage.data?.[0]?.sender_id??null,reports};
   }));
   const me=(mem.data??[]).find((m:any)=>m.user_id===target);
   await audit("view_user_profile",target,{conversation_count:convs.length,transcript_loaded:false});
   return out({ok:true,user:{...(pr.data??{id:target}),auth:au,last_read_at:me?.last_read_at??null},conversations:mapped,messageLimit:0},200,origin);
  }
  if(action==="message_reports"){
   const status=clean(input.status,20);
   let q=admin.from("message_reports").select("id,conversation_id,message_id,reported_by,reason,status,created_at,reviewed_at,reviewed_by,moderation_notes").order("created_at",{ascending:false}).limit(150);
   if(status&&["pending","in_review","resolved","dismissed"].includes(status))q=q.eq("status",status);
   const {data:reports,error}=await q;if(error)throw error;
   const messageIds=unique((reports??[]).map((r:any)=>r.message_id));
   const {data:messages,error:messageError}=messageIds.length?await admin.from("messages").select("id,conversation_id,sender_id,created_at,deleted_at,delete_for_everyone").in("id",messageIds):{data:[],error:null};
   if(messageError)throw messageError;
   const userIds=unique([...(reports??[]).map((r:any)=>r.reported_by),...(messages??[]).map((m:any)=>m.sender_id)]);
   const {data:profiles,error:profileError}=userIds.length?await admin.from("profiles").select("id,username,display_name,avatar_url").in("id",userIds):{data:[],error:null};
   if(profileError)throw profileError;
   const pmap=new Map((profiles??[]).map((p:any)=>[p.id,p])),mmap=new Map((messages??[]).map((m:any)=>[m.id,m]));
   const items=(reports??[]).map((r:any)=>{
    const m:any=mmap.get(r.message_id)||{},reporter:any=pmap.get(r.reported_by)||{},sender:any=pmap.get(m.sender_id)||{};
    return{...r,message_created_at:m.created_at??null,message_deleted:Boolean(m.deleted_at||m.delete_for_everyone),sender_id:m.sender_id??null,sender_name:sender.display_name||sender.username||"Unknown user",sender_avatar_url:sender.avatar_url??null,reporter_name:reporter.display_name||reporter.username||"Unknown user",reporter_username:reporter.username??null,reporter_avatar_url:reporter.avatar_url??null};
   });
   await audit("list_message_reports",null,{status:status||"all",returned:items.length});
   return out({ok:true,reports:items},200,origin);
  }
  if(action==="conversation_messages"){
   const reportId=clean(input.reportId,80),conversationId=clean(input.conversationId,80);
   if(!reportId||!conversationId)return out({error:"Report ID ও conversation ID লাগবে।"},400,origin);
   const {data:report,error:reportError}=await admin.from("message_reports").select("id,conversation_id,message_id,reported_by,reason,status,created_at,reviewed_at,reviewed_by,moderation_notes").eq("id",reportId).eq("conversation_id",conversationId).maybeSingle();
   if(reportError)throw reportError;if(!report)return out({error:"এই কথোপকথনের অনুমোদিত report পাওয়া যায়নি।"},404,origin);
   if(report.status==="dismissed")return out({error:"Dismiss করা report-এর transcript access বন্ধ আছে।"},403,origin);
   const [convResult,membersResult,messagesResult]=await Promise.all([
    admin.from("conversations").select("id,created_by,is_group,is_direct,title,created_at").eq("id",conversationId).maybeSingle(),
    admin.from("conversation_members").select("conversation_id,user_id,joined_at,last_read_at").eq("conversation_id",conversationId),
    admin.from("messages").select("id,conversation_id,sender_id,body,created_at,edited_at,deleted_at,deleted_by,delete_for_everyone,delivered_at,read_at,image_path,image_name,image_mime_type,image_size").eq("conversation_id",conversationId).order("created_at",{ascending:true}).limit(2000)
   ]);
   if(convResult.error)throw convResult.error;if(membersResult.error)throw membersResult.error;if(messagesResult.error)throw messagesResult.error;
   if(!convResult.data)return out({error:"কথোপকথন পাওয়া যায়নি।"},404,origin);
   const members=membersResult.data??[];let messages=messagesResult.data??[];
   const ids=unique([...members.map((m:any)=>m.user_id),...messages.map((m:any)=>m.sender_id)]);
   const {data:profiles,error:profileError}=ids.length?await admin.from("profiles").select("id,username,display_name,avatar_url,about,is_online,is_banned,last_seen,created_at").in("id",ids):{data:[],error:null};
   if(profileError)throw profileError;
   const pmap=new Map((profiles??[]).map((p:any)=>[p.id,p]));
   const participants=members.map((m:any)=>{const p:any=pmap.get(m.user_id)||{};return{user_id:m.user_id,username:p.username??null,display_name:p.display_name??"Unknown user",avatar_url:p.avatar_url??null,about:p.about??"",is_online:p.is_online??false,is_banned:p.is_banned??false,last_seen:p.last_seen??null,created_at:p.created_at??null,last_read_at:m.last_read_at??null}});
   const paths=unique(messages.filter((m:any)=>m.image_path&&!m.deleted_at&&!m.delete_for_everyone).map((m:any)=>m.image_path));
   if(paths.length){try{const {data:signed,error}=await admin.storage.from("chat-images").createSignedUrls(paths,300);if(!error&&signed){const smap=new Map(signed.map((x:any,i:number)=>[x.path||paths[i],x.signedUrl]));messages=messages.map((m:any)=>({...m,image_url:m.image_path?(smap.get(m.image_path)??null):null}))}}catch(e){console.warn("image signing",e)}}
   messages=messages.map((m:any)=>{const p:any=pmap.get(m.sender_id)||{};return{...m,sender_name:p.display_name||p.username||"Unknown user",sender_username:p.username??null,sender_avatar_url:p.avatar_url??null}});
   if(report.status==="pending"){const {error}=await admin.from("message_reports").update({status:"in_review",reviewed_by:caller.id,reviewed_at:new Date().toISOString()}).eq("id",reportId);if(error)throw error;report.status="in_review";}
   await audit("view_reported_conversation",report.reported_by,{report_id:reportId,conversation_id:conversationId,message_count:messages.length});
   return out({ok:true,report,conversation:{...convResult.data,participants},messages,messageLimit:2000},200,origin);
  }
  if(action==="message_report_status"){
   const reportId=clean(input.reportId,80),status=clean(input.status,20),notes=clean(input.notes,1000);
   if(!reportId||!["in_review","resolved","dismissed"].includes(status))return out({error:"Valid report ID ও status লাগবে।"},400,origin);
   const {data:existing,error:existingError}=await admin.from("message_reports").select("id,reported_by,conversation_id,status").eq("id",reportId).maybeSingle();
   if(existingError)throw existingError;if(!existing)return out({error:"Report পাওয়া যায়নি।"},404,origin);
   const {data:updated,error}=await admin.from("message_reports").update({status,moderation_notes:notes||null,reviewed_by:caller.id,reviewed_at:new Date().toISOString()}).eq("id",reportId).select("id,status,moderation_notes,reviewed_by,reviewed_at").single();
   if(error)throw error;
   await audit("message_report_status",existing.reported_by,{report_id:reportId,conversation_id:existing.conversation_id,status,has_notes:Boolean(notes)});
   return out({ok:true,report:updated},200,origin);
  }
  if(action==="ban_user"||action==="unban_user"){
   const target=clean(input.userId,80);if(!target)return out({error:"User ID লাগবে।"},400,origin);if(target===caller.id)return out({error:"নিজের Admin account ব্যান করা যাবে না।"},400,origin);
   const banned=action==="ban_user";
   const {data:p,error}=await admin.from("profiles").update({is_banned:banned,ban_reason:banned?(clean(input.reason,500)||"Admin decision"):null,banned_at:banned?new Date().toISOString():null,banned_by:banned?caller.id:null}).eq("id",target).select("id,is_banned,ban_reason,banned_at").maybeSingle();
   if(error)throw error;if(!p)return out({error:"User profile পাওয়া যায়নি।"},404,origin);
   // Keep sign-in available on ban so the app can show the banner; account RLS blocks access while is_banned=true.
   // On unban, also clear any legacy Auth-level ban set by older deployed versions.
   if(!banned){const {error:authError}=await admin.auth.admin.updateUserById(target,{ban_duration:"none"});if(authError)throw authError;}
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
   const deletedAuth=await authInfo(target);if(!deletedAuth)return out({error:"Auth account পাওয়া যায়নি।"},404,origin);
   const {data:deletedProfile,error:deletedProfileError}=await admin.from("profiles").select("username,display_name").eq("id",target).maybeSingle();
   if(deletedProfileError)throw deletedProfileError;
   const usernameNorm=clean(deletedProfile?.username,30).toLowerCase()||null;
   const emailNorm=clean(deletedAuth.email,320).toLowerCase()||null;
   const tombstoneData={original_user_id:target,username:deletedProfile?.username??null,username_norm:usernameNorm,display_name:deletedProfile?.display_name??null,email:deletedAuth.email??null,email_norm:emailNorm,deleted_at:new Date().toISOString(),deleted_by:caller.id,deletion_reason:clean(input.reason,500)||"Deleted by admin"};
   let existingTombstone:any=null;
   const {data:byOriginal,error:originalError}=await admin.from("account_tombstones").select("id").eq("original_user_id",target).maybeSingle();
   if(originalError)throw originalError;
   existingTombstone=byOriginal;
   if(!existingTombstone&&emailNorm){const {data,error}=await admin.from("account_tombstones").select("id").eq("email_norm",emailNorm).maybeSingle();if(error)throw error;existingTombstone=data;}
   if(!existingTombstone&&usernameNorm){const {data,error}=await admin.from("account_tombstones").select("id").eq("username_norm",usernameNorm).maybeSingle();if(error)throw error;existingTombstone=data;}
   if(existingTombstone){const {error}=await admin.from("account_tombstones").update(tombstoneData).eq("id",existingTombstone.id);if(error)throw error;}
   else{const {error}=await admin.from("account_tombstones").insert(tombstoneData);if(error)throw error;}
   await audit("delete_user_started",target,{warning:"Account identifiers are retained in a restricted tombstone so a deleted-account banner can be shown. Conversations and messages in those conversations are permanently removed."});
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