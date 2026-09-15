import type {Price} from './types';
export function liveComparisons(prices:Price[],now:number,maxAge:number){
 const groups=new Map<string,Price[]>();
 for(const p of prices){if(p.source!=='live'||p.stale||!Number.isFinite(p.bid)||!Number.isFinite(p.ask)||p.bid<=0||p.ask<=0||now-p.timestamp>maxAge||p.timestamp>now+1000)continue;const key=p.symbol+'|'+p.quote;groups.set(key,[...(groups.get(key)||[]),p]);}
 return Array.from(groups.values()).flatMap(items=>{let best:{buy:Price;sell:Price;gross:number}|null=null;for(const buy of items)for(const sell of items){if(buy.exchange===sell.exchange)continue;const gross=(sell.bid/buy.ask-1)*100;if(!best||gross>best.gross)best={buy,sell,gross};}return best?[best]:[];}).sort((a,b)=>b.gross-a.gross);
}
