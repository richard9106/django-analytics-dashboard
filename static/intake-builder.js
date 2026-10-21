(() => {
  const types = [['short_text','Short text'],['long_text','Long text'],['single_choice','Single choice'],['multiple_choice','Multiple choice'],['dropdown','Dropdown'],['yes_no','Yes / No']];
  const choices = new Set(['single_choice','multiple_choice','dropdown']);
  const make = (tag, text, cls) => { const e=document.createElement(tag); if(text)e.textContent=text; if(cls)e.className=cls; return e; };
  const uid = () => 'id-'+crypto.randomUUID();
  document.querySelectorAll('[data-intake-builder]').forEach(root => {
    const form=root.closest('form'), hidden=form.querySelector('[name$="form_structure"]'), fallback=root.querySelector('[data-builder-fallback]');
    let data; try { data=JSON.parse(hidden.value); } catch { return; }
    if (!Array.isArray(data.pages)) return;
    hidden.disabled=false; fallback.hidden=true;
    const toolbar=make('div',null,'builder-toolbar'), pages=make('div'), feedback=make('p',null,'builder-feedback'), preview=make('section',null,'builder-preview');
    feedback.setAttribute('role','status'); preview.hidden=true; preview.setAttribute('aria-label','Client form preview');
    const expanded=new Set([data.pages[0]?.questions[0]?.id]);
    const sync=()=>{ hidden.value=JSON.stringify(data); };
    const button=(label,action,cls='btn btn-secondary')=>{ const e=make('button',label,cls);e.type='button';e.addEventListener('click',action);return e; };
    const input=(parent,label,value,change,{multiline=false,required=false,maxLength=500}={})=>{
      const wrap=make('label',null,'field builder-field');wrap.append(make('span',label));
      const e=make(multiline?'textarea':'input'); if(!multiline)e.type='text'; else e.rows=3;
      e.value=value||'';e.required=required;e.maxLength=maxLength;
      e.addEventListener('input',()=>{change(e.value);sync();});wrap.append(e);parent.append(wrap);return e;
    };
    const move=(items,index,delta)=>{ const target=index+delta;if(target<0||target>=items.length)return;[items[index],items[target]]=[items[target],items[index]];sync();render(); };
    const renderPreview=()=>{
      preview.replaceChildren(make('h2','Client preview'),make('p','Preview only — responses are not saved.'));
      data.pages.forEach((p,i)=>{
        const section=make('section',null,'builder-preview-page');section.append(make('p',`Page ${i+1} of ${data.pages.length}`,'eyebrow'),make('h3',p.title||'Untitled page'));
        if(p.description)section.append(make('p',p.description));
        p.questions.forEach(q=>{
          const field=make('div',null,'field');field.append(make('strong',(q.label||'Untitled question')+(q.required?' *':' (optional)')));
          if(q.help_text)field.append(make('small',q.help_text));
          if(['single_choice','multiple_choice','yes_no'].includes(q.type)){
            (q.type==='yes_no'?['Yes','No']:q.options).forEach(o=>{const label=make('label',null,'builder-preview-option');const control=make('input');control.type=q.type==='multiple_choice'?'checkbox':'radio';control.disabled=true;label.append(control,document.createTextNode(' '+o));field.append(label);});
          }else{
            const control=make(q.type==='dropdown'?'select':q.type==='long_text'?'textarea':'input');control.disabled=true;control.setAttribute('aria-label',q.label||'Question');
            if(q.type==='dropdown')q.options.forEach(o=>control.append(make('option',o)));
            field.append(control);
          }section.append(field);
        });preview.append(section);
      });
    };
    const render=()=>{
      pages.replaceChildren(); preview.hidden=true;
      data.pages.forEach((p,pi)=>{
        const page=make('section',null,'builder-page');
        const head=make('div',null,'builder-row');head.append(make('h3',`Page ${pi+1}`));
        const actions=make('div',null,'builder-actions');
        const up=button('Move page up',()=>move(data.pages,pi,-1));up.disabled=pi===0;
        const down=button('Move page down',()=>move(data.pages,pi,1));down.disabled=pi===data.pages.length-1;
        const remove=button('Remove page',()=>{if(confirm('Remove this page and its questions?')){data.pages.splice(pi,1);sync();render();}});remove.disabled=data.pages.length===1;
        actions.append(up,down,remove);head.append(actions);page.append(head);
        input(page,'Page title',p.title,v=>p.title=v,{required:true,maxLength:160});
        input(page,'Instructions (optional)',p.description,v=>p.description=v,{multiline:true,maxLength:2000});
        p.questions.forEach((q,qi)=>{
          const card=make('details',null,'builder-question');card.open=expanded.has(q.id)||!q.label;card.addEventListener('toggle',()=>{if(card.open)expanded.add(q.id);else expanded.delete(q.id);});const summary=make('summary',null,'builder-question-summary');const caption=make('strong',q.label||'New question');summary.append(caption,make('span',(types.find(([type])=>type===q.type)?.[1]||'Long text')+(q.required?' · Required':' · Optional')));card.append(summary);const row=make('div',null,'builder-row');row.append(make('h4',`Question ${qi+1}`));
          const qa=make('div',null,'builder-actions');const qup=button('Move up',()=>move(p.questions,qi,-1));qup.disabled=qi===0;const qdown=button('Move down',()=>move(p.questions,qi,1));qdown.disabled=qi===p.questions.length-1;
          qa.append(qup,qdown,button('Remove',()=>{if(!q.label||confirm('Remove this question?')){p.questions.splice(qi,1);sync();render();}}));row.append(qa);card.append(row);
          input(card,'Question title',q.label,v=>{q.label=v;caption.textContent=v||'New question';},{required:true});
          const label=make('label',null,'field');label.append(make('span','Answer type'));const select=make('select');types.forEach(([value,text])=>{const o=make('option',text);o.value=value;o.selected=q.type===value;select.append(o);});
          select.addEventListener('change',()=>{q.type=select.value;sync();render();});label.append(select);card.append(label);
          input(card,'Help text (optional)',q.help_text,v=>q.help_text=v,{multiline:true,maxLength:2000});
          if(choices.has(q.type))input(card,'Answer options — one per line',q.options.join('\n'),v=>q.options=v.split('\n').map(s=>s.trim()).filter(Boolean),{multiline:true,required:true,maxLength:12000});
          const required=make('label',null,'builder-required');const checkbox=make('input');checkbox.type='checkbox';checkbox.checked=q.required;checkbox.addEventListener('change',()=>{q.required=checkbox.checked;summary.lastElementChild.textContent=(types.find(([type])=>type===q.type)?.[1]||'Long text')+(q.required?' · Required':' · Optional');sync();});required.append(checkbox,document.createTextNode('Required question'));card.append(required);
          if(data.pages.length>1){const destination=make('label',null,'field');destination.append(make('span','Move question to page'));const list=make('select');data.pages.forEach((target,i)=>{const o=make('option',`${i+1}. ${target.title||'Untitled page'}`);o.value=i;o.selected=i===pi;list.append(o);});list.addEventListener('change',()=>{data.pages[Number(list.value)].questions.push(q);p.questions.splice(qi,1);sync();render();});destination.append(list);card.append(destination);}
          page.append(card);
        });
        page.append(button('+ Add question',()=>{if(data.pages.reduce((n,p)=>n+p.questions.length,0)>=100){feedback.textContent='Limit: 100 questions per form.';return;}p.questions.push({id:uid(),label:'',type:'long_text',required:true,help_text:'',options:[]});sync();render();expanded.add(p.questions[p.questions.length-1].id);pages.querySelectorAll('.builder-page')[pi]?.querySelector('.builder-question:last-of-type input')?.focus();},'btn btn-primary'));
        pages.append(page);
      });
    };
    toolbar.append(button('+ Add page',()=>{if(data.pages.length>=20){feedback.textContent='Limit: 20 pages per form.';return;}data.pages.push({id:uid(),title:`Page ${data.pages.length+1}`,description:'',questions:[]});sync();render();pages.lastElementChild?.querySelector('input')?.focus();}),button('Preview form',()=>{const opening=preview.hidden;renderPreview();preview.hidden=!opening;if(opening)preview.scrollIntoView({block:'start',behavior:'smooth'});}));
    root.append(toolbar,feedback,pages,preview);render();sync();
    form.addEventListener('invalid',event=>{const question=event.target.closest('.builder-question');if(question)question.open=true;},true);
    form.addEventListener('submit',event=>{sync();if(data.pages.some(p=>!p.questions.length)){event.preventDefault();feedback.textContent='Add at least one question to every page.';feedback.scrollIntoView({block:'center'});}});
  });
})();
