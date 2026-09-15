export type DemoState = {stage:'ready'|'bought'|'complete';quantity:number;scenario:'profit'|'adverse';aCash:number;bCash:number;aCoin:number;bCoin:number;buyCost:number;sellProceeds:number;events:string[]};
export const BUY_PRICE=60000,SELL_PRICE=60600,FEE_RATE=.001;
export function newDemo(quantity=.01,scenario:DemoState['scenario']='profit'):DemoState{
 if(![.001,.01,.02].includes(quantity))throw new Error('Unsupported quantity');
 return {stage:'ready',quantity,scenario,aCash:5000,bCash:5000,aCoin:0,bCoin:.05,buyCost:0,sellProceeds:0,events:['Demo wallets funded: 5,000 USDT on each venue and 0.05 BTC on Venue B.']};
}
export function demoTrade(state:DemoState,action:'buy'|'sell'):DemoState{
 const q=state.quantity;
 if(action==='buy'){
  if(state.stage!=='ready')return state;
  const cost=q*BUY_PRICE*(1+FEE_RATE);
  if(cost>state.aCash)throw new Error('Insufficient demo USDT');
  return {...state,stage:'bought',aCash:state.aCash-cost,aCoin:state.aCoin+q,buyCost:cost,events:[...state.events,`BUY filled: ${q} BTC at ${BUY_PRICE} USDT. Fee ${(q*BUY_PRICE*FEE_RATE).toFixed(4)} USDT.`]};
 }
 if(state.stage!=='bought')return state;
 if(q>state.bCoin)throw new Error('Insufficient prefunded demo BTC at Venue B');
 const price=state.scenario==='adverse'?59800:SELL_PRICE;
 const proceeds=q*price*(1-FEE_RATE);
 return {...state,stage:'complete',bCash:state.bCash+proceeds,bCoin:state.bCoin-q,sellProceeds:proceeds,events:[...state.events,`SELL filled: ${q} BTC at ${price} USDT. Fee ${(q*price*FEE_RATE).toFixed(4)} USDT.`, `Cycle complete. Realized demo P&L: ${(proceeds-state.buyCost).toFixed(4)} USDT. No money moved.`]};
}
