# usage: python trace.py <exe_name> <seconds> <out.log>
# Runs the game from its folder under Frida, logs file opens + FMOD calls (to find why music/voice is silent).
import frida, sys, time, os

exe, secs, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
game = r'X:\GAMES\Divine Divinity'
js = r'''
function s(p){try{return p.readAnsiString()}catch(e){return '?'}}
function w(p){try{return p.readUtf16String()}catch(e){return '?'}}
const k = Process.getModuleByName('kernel32.dll');
['CreateFileA','CreateFileW'].forEach(n=>{
  const a = k.getExportByName(n); const wide = n.endsWith('W');
  Interceptor.attach(a,{onEnter(ar){this.p = wide ? w(ar[0]) : s(ar[0]);},
    onLeave(r){ if(/\.(cmp|ogg|dat|cfg|div|wav|lcl)|voice|music|sound/i.test(this.p)) send('CF '+this.p+' -> '+(r.toInt32()==-1?'FAIL':'ok'));}});
});
function hookFmod(){
  let m; try{m = Process.getModuleByName('fmod.dll')}catch(e){return false}
  m.enumerateExports().forEach(e=>{
    const n = e.name;
    if(/FSOUND_(Init|Close|Stream_OpenFile|Stream_Play|Stream_Close|Stream_Stop|PlaySound|PlaySoundEx|Sample_Load|File_SetCallbacks|SetOutput|SetDriver|StopSound)@/.test(n)){
      Interceptor.attach(e.address,{onEnter(ar){
          let extra='';
          if(/OpenFile/.test(n)) extra=' "'+s(ar[0])+'" mode=0x'+ar[1].toString(16);
          if(/Sample_Load/.test(n)) extra=' arg1='+ar[1].toString(16);
          if(/Init@/.test(n)) extra=' rate='+ar[0].toInt32()+' ch='+ar[1].toInt32()+' flags='+ar[2].toInt32();
          this.n = n; send('FM '+n+extra);},
        onLeave(r){ if(/OpenFile|Stream_Play|PlaySound|Init|Sample_Load/.test(this.n)) send('FM   ret '+this.n+' = '+r);}});
    }
  });
  send('fmod hooked '+m.base); return true;
}
let tries = 0; const t = setInterval(()=>{ if(hookFmod()||++tries>200) clearInterval(t) }, 50);
'''
dev = frida.get_local_device()
log = open(out, 'w', encoding='utf-8', buffering=1)
t0 = time.time()
def on_msg(m, d):
    if m['type'] == 'send':
        log.write('%7.2f %s\n' % (time.time() - t0, m['payload']))
    else:
        log.write(str(m) + '\n')
pid = dev.spawn([os.path.join(game, exe)], cwd=game)
sess = dev.attach(pid)
sc = sess.create_script(js)
sc.on('message', on_msg)
sc.load()
dev.resume(pid)
log.write('pid %d started\n' % pid)
try:
    time.sleep(secs)
finally:
    try:
        dev.kill(pid)
    except Exception as e:
        log.write('kill: %s\n' % e)
    log.close()
