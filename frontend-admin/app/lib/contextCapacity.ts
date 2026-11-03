export type ContextSample = {
  index_id:string;current_index_id:string;tokenizer:string;tokenization:string;
  sample:{chunk_id:string;tokens:number;characters:number;utf8_bytes:number}|null;
  model:{id:string;name:string;context_tokens:number|null;max_output_tokens:number;max_input_chars:number;reserved_tokens:number;input_guard_bytes:number|null};
};

export function estimateContextCapacity(data:ContextSample, count:number) {
  const sample=data.sample;
  if(!sample || sample.tokens<=0 || sample.characters<=0 || sample.utf8_bytes<=0 || !Number.isInteger(count) || count<1)return null;
  const budgets:{tokens:number;basis:"context"|"characters"|"safety";approximate:boolean}[]=[];
  if(data.model.context_tokens!==null)budgets.push({tokens:Math.max(0,data.model.context_tokens-data.model.max_output_tokens-data.model.reserved_tokens),basis:"context",approximate:false});
  if(data.model.max_input_chars>0)budgets.push({tokens:data.model.max_input_chars*sample.tokens/sample.characters,basis:"characters",approximate:true});
  if(data.model.input_guard_bytes!==null)budgets.push({tokens:data.model.input_guard_bytes*sample.tokens/sample.utf8_bytes,basis:"safety",approximate:true});
  if(!budgets.length)return null;
  const applicationBudgets=budgets.filter(b=>b.basis!=="context");
  const application=applicationBudgets.length?applicationBudgets.reduce((a,b)=>a.tokens<=b.tokens?a:b):null;
  const budget=budgets.find(b=>b.basis==="context") || application!;
  const tokens=count*sample.tokens;
  return {tokens,count,sampleTokens:sample.tokens,budgetTokens:Math.floor(budget.tokens),basis:budget.basis,
    percentage:budget.tokens>0?tokens/budget.tokens*100:null,
    applicationPercentage:budget.basis==="context"&&application&&application.tokens<budget.tokens ? (application.tokens>0?tokens/application.tokens*100:null) : null,
    applicationExceeded:Boolean(application&&tokens>application.tokens),
    exceeds:tokens>budget.tokens || Boolean(application&&tokens>application.tokens),approximate:budget.approximate};
}
