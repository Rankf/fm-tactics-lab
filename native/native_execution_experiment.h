// Opt-in experiment. Each configured match runs in its own worker session.
// Current image 2493426: d85a0 computes the 33-byte tactical-effectiveness
// record at MATCH_PLAYER+cba. 41a50 consumes it during action sampling.
static unsigned char* execution_teams[2]={};
static int execution_policy[2]={-1,-1};
static unsigned long long execution_builds[2]={},execution_samples[2]={};
static unsigned short execution_input_ca[2][26]={};
static bool execution_input_seen[2][26]={};
static unsigned char execution_calculated_overall[2][26]={};
using ExecutionBuild=void(*)(void*,void*,void*,void*,void*,void*,void*,void*,void*,unsigned short);
using ExecutionSample=void(*)(void*,uintptr_t,uintptr_t,void*,uintptr_t);
static ExecutionBuild execution_original_build=nullptr;
static ExecutionSample execution_original_sample=nullptr;
static int execution_side(unsigned char* player){
 auto team=*(unsigned char**)(player+0x288);
 return !team?-1:team==execution_teams[0]?0:team==execution_teams[1]?1:-1;
}
static void execution_apply(unsigned char* player,int side){
 if(side>=0&&execution_policy[side]>=0)memset(player+0xcba,execution_policy[side],33);
}
static void execution_build(void* record,void* plan,void* history,void* exposure,void* attributes,
                            void* opposition,void* training,void* ip,void* oop,unsigned short ca){
 execution_original_build(record,plan,history,exposure,attributes,opposition,training,ip,oop,ca);
 auto player=(unsigned char*)record-0xcba;int side=execution_side(player);
 if(side<0)return;
 execution_builds[side]++;
 for(unsigned i=0;i<26;i++)if(original_roster[side][i]==player){
  execution_input_ca[side][i]=ca;
  execution_input_seen[side][i]=true;
  execution_calculated_overall[side][i]=player[0xcd8];
  break;
 }
 execution_apply(player,side);
}
static void execution_sample(void* actor,uintptr_t a,uintptr_t b,void* rng,uintptr_t c){
 auto player=(unsigned char*)actor;int side=execution_side(player);
 execution_apply(player,side);
 if(side>=0){
  execution_samples[side]++;
  if(execution_policy[side]>=0)for(unsigned i=0;i<33;i++)
   if(player[0xcba+i]!=execution_policy[side])desktop_finish_and_exit(245);
 }
 execution_original_sample(actor,a,b,rng,c);
}
static void* execution_redirect(unsigned rva,void* replacement,unsigned stack_low,unsigned stack_high){
 // Both entries have exactly eight pushes and a seven-byte SUB RSP prologue;
 // no RIP-relative instruction or branch is relocated into the trampoline.
 unsigned char expected[]={0x41,0x57,0x41,0x56,0x41,0x55,0x41,0x54,0x56,0x57,0x55,0x53,
                            0x48,0x81,0xec,(unsigned char)stack_low,(unsigned char)stack_high,0,0};
 auto entry=(unsigned char*)at(rva);
 if(memcmp(entry,expected,sizeof(expected)))desktop_finish_and_exit(246);
 auto trampoline=(unsigned char*)VirtualAlloc(nullptr,64,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
 if(!trampoline)desktop_finish_and_exit(247);
 memcpy(trampoline,entry,19);
 unsigned char jump[]={0xff,0x25,0,0,0,0,0,0,0,0,0,0,0,0};
 auto continuation=entry+19;memcpy(jump+6,&continuation,8);memcpy(trampoline+19,jump,14);
 DWORD old=0;if(!VirtualProtect(trampoline,64,PAGE_EXECUTE_READ,&old))desktop_finish_and_exit(247);
 FlushInstructionCache(GetCurrentProcess(),trampoline,64);
 memcpy(jump+6,&replacement,8);
 if(!VirtualProtect(entry,19,PAGE_EXECUTE_READWRITE,&old))desktop_finish_and_exit(247);
 memcpy(entry,jump,14);memset(entry+14,0x90,5);
 DWORD unused;if(!VirtualProtect(entry,19,old,&unused))desktop_finish_and_exit(247);
 FlushInstructionCache(GetCurrentProcess(),entry,19);return trampoline;
}
static void execution_install(unsigned char* match){
 bool enabled=false;
 for(const auto& edit:scenario_edits){
  if(edit.kind!=61)continue;
  if(execution_policy[edit.side]>=0)desktop_finish_and_exit(244);
  execution_policy[edit.side]=(int)edit.value;
  enabled=true;
 }
 if(!enabled)return;
 if(execution_original_sample||strcmp(native_image_sha256,
    "252ff8fb5b7a4a5a5464db6ba632e309eef9b6e65ffa992ae20575a189e66c6a"))desktop_finish_and_exit(244);
 for(unsigned side=0;side<2;side++)execution_teams[side]=*(unsigned char**)(match+0x15380+8*side);
 constexpr unsigned version=0x1b000000u;
 fprintf(log_file,"{\"event\":\"experimental_engine_version\",\"before\":%u,\"after\":%u,\"production_supported\":false}\n",*(unsigned*)(match+0xa3a),version);
 *(unsigned*)(match+0xa3a)=version;
 execution_original_build=(ExecutionBuild)execution_redirect(0xd85a0,(void*)execution_build,0x38,1);
 execution_original_sample=(ExecutionSample)execution_redirect(0x41a50,(void*)execution_sample,0x88,0);
}
static void execution_snapshot(unsigned char* match,const char* stage){
 if(!execution_original_sample)return;
 for(unsigned side=0;side<2;side++){
  auto team=*(unsigned char**)(match+0x15380+8*side);
  fprintf(log_file,"{\"event\":\"native_execution_probe\",\"stage\":\"%s\",\"side\":%u,\"policy\":%d,\"build_calls\":%llu,\"sample_calls\":%llu,\"players\":[",stage,side,execution_policy[side],execution_builds[side],execution_samples[side]);
  for(unsigned i=0;i<team[0x72d];i++){
   auto p=*(unsigned char**)(team+0x138+8*i);
   fprintf(log_file,"%s{\"slot\":%u,\"overall\":%u,\"buy_in\":%u,\"next_match_information\":%u,\"raw_ability_component\":%u,\"role_suitability_component\":%u,",i?",":"",i,p[0xcd8],p[0xcd9],p[0xcda],p[0xcd6],p[0xcd7]);
   for(unsigned j=0;j<26;j++)if(original_roster[side][j]==p&&execution_input_seen[side][j]){
    fprintf(log_file,"\"input_roster_slot\":%u,\"input_ca\":%u,\"calculated_overall_before_override\":%u,",
            j,execution_input_ca[side][j],execution_calculated_overall[side][j]);break;
   }
   fputs("\"record_hex\":\"",log_file);
   for(unsigned j=0;j<34;j++)fprintf(log_file,"%02x",p[0xcba+j]);fputs("\"}",log_file);
  }
  fputs("]}\n",log_file);fflush(log_file);
 }
}
