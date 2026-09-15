import { useEffect, useState } from 'react';
import { createClient, type User } from '@supabase/supabase-js';
import './auth.css';
const url = import.meta.env.VITE_SUPABASE_URL;
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;
const recovering = new URLSearchParams(location.search).get('recovery') === '1';
export const authClient = url && key ? createClient(url, key, {auth:{flowType:'pkce'}}) : null;
export function AccountMenu() {
  const [open,setOpen]=useState(recovering), [mode,setMode]=useState<'login'|'signup'|'reset'|'update'>(recovering?'update':'login');
  const [user,setUser]=useState<User|null>(null), [email,setEmail]=useState(''), [password,setPassword]=useState('');
  const [busy,setBusy]=useState(false), [message,setMessage]=useState('');
  useEffect(()=>{
    if(!authClient)return;
    const {data:{subscription}}=authClient.auth.onAuthStateChange((event,session)=>{
      setUser(session?.user??null);
      if(event==='PASSWORD_RECOVERY'){setMode('update');setOpen(true);}
    });
    return ()=>subscription.unsubscribe();
  },[]);
  async function submit(e:React.FormEvent){
    e.preventDefault(); if(!authClient||busy)return;
    setBusy(true);setMessage('');
    try {
      const redirect=window.location.origin+'/';
      const result=mode==='signup'?await authClient.auth.signUp({email,password,options:{emailRedirectTo:redirect}})
        :mode==='reset'?await authClient.auth.resetPasswordForEmail(email,{redirectTo:redirect+'?recovery=1'})
        :mode==='update'?await authClient.auth.updateUser({password})
        :await authClient.auth.signInWithPassword({email,password});
      if(result.error)throw result.error;
      setPassword('');
      setMessage(mode==='signup'?'Check your email to confirm your account.':mode==='reset'?'If the address is eligible, a password reset email will arrive.':mode==='update'?'Password updated.':'Signed in successfully.');
    }catch(error){setMessage(error instanceof Error?error.message:'Unable to complete the request. Please retry.');}
    finally{setBusy(false);}
  }
  async function logout(){
    if(!authClient)return;
    setBusy(true);
    const {error}=await authClient.auth.signOut();
    setBusy(false);setMessage(error?error.message:'Signed out.');
  }
  return <div className="account-entry"><button className="account-trigger" onClick={()=>{setOpen(true);setMessage('');}}>{user?'Account':'Sign in / Sign up'}</button>
    {open&&<dialog open className="account-dialog" aria-labelledby="account-title"><button className="account-close" aria-label="Close account" onClick={()=>{setOpen(false);setPassword('');}}>×</button>
      <span className="eyebrow">ARBITRAGE X ACCOUNT</span><h2 id="account-title">{user&&mode!=='update'?'Your account':mode==='signup'?'Create your account':mode==='reset'?'Reset password':mode==='update'?'Choose a new password':'Welcome back'}</h2>
      {!authClient?<p role="status">Account registration is not available yet. The site owner needs to connect the authentication service. You can continue exploring markets and the trading demo.</p>
      :user&&mode!=='update'?<><p>{user.email}</p><button className="account-primary" disabled={busy} onClick={()=>void logout()}>Log out</button></>
      :<form onSubmit={submit}>{mode!=='update'&&<label>Email<input type="email" autoComplete="email" required value={email} onChange={e=>setEmail(e.target.value)}/></label>}
      {mode!=='reset'&&<label>Password<input type="password" autoComplete={mode==='login'?'current-password':'new-password'} minLength={mode==='login'?1:12} required value={password} onChange={e=>setPassword(e.target.value)}/></label>}
      <button className="account-primary" disabled={busy}>{busy?'Please wait…':mode==='signup'?'Create account':mode==='reset'?'Send reset email':mode==='update'?'Update password':'Sign in'}</button>
      <div className="account-links">{(['login','signup','reset'] as const).filter(m=>m!==mode).map(m=><button type="button" key={m} onClick={()=>{setMode(m);setPassword('');setMessage('');}}>{m==='login'?'Sign in':m==='signup'?'Create account':'Forgot password?'}</button>)}</div></form>}
      {message&&<p role="status">{message}</p>}
    </dialog>}
  </div>;
}
