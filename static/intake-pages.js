(() => {
  document.querySelectorAll('[data-intake-pages]').forEach(form=>{
    const pages=Array.from(form.querySelectorAll('[data-intake-page]'));
    if(pages.length<2)return;
    const controls=form.querySelector('[data-page-controls]'),previous=form.querySelector('[data-page-previous]'),next=form.querySelector('[data-page-next]'),submit=form.querySelector('[data-page-submit]'),progress=form.querySelector('[data-page-progress]');
    controls.hidden=false;
    let index=Math.max(0,pages.findIndex(p=>p.querySelector('.errorlist')));
    const show=()=>{pages.forEach((p,i)=>{p.hidden=i!==index;});previous.disabled=index===0;next.hidden=index===pages.length-1;submit.hidden=index!==pages.length-1;progress.textContent=`Page ${index+1} of ${pages.length}`;};
    const updateMultiple=()=>{form.querySelectorAll('[data-required-multiple]').forEach(group=>{const boxes=Array.from(group.querySelectorAll('input'));if(boxes.length)boxes[0].setCustomValidity(boxes.some(box=>box.checked)?'':'Select at least one option.');});};
    form.addEventListener('change',updateMultiple);updateMultiple();
    const valid=()=>{for(const field of pages[index].querySelectorAll('input,textarea,select'))if(!field.reportValidity())return false;return true;};
    const focus=()=>{const heading=pages[index].querySelector('h2');heading.focus();};
    previous.addEventListener('click',()=>{if(index>0){index--;show();focus();}});
    next.addEventListener('click',()=>{if(valid()){index++;show();focus();}});
    // Disable automatic browser validation across hidden pages; validate every
    // field explicitly and reveal the right page before reporting an error.
    form.noValidate=true;
    form.addEventListener('submit',event=>{
      if(index<pages.length-1){event.preventDefault();next.click();return;}
      for(let i=0;i<pages.length;i++)for(const field of pages[i].querySelectorAll('input,textarea,select'))if(!field.checkValidity()){event.preventDefault();index=i;show();field.reportValidity();return;}
    });
    show();
  });
})();
