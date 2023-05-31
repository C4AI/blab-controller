for (const hc of document.querySelectorAll('.sidebar-tree li, .toc-tree li')) {
    const a = hc.querySelector('a.reference');
    const a_pre = a.querySelector('.pre');
    const ul = hc.querySelector('ul');
    if (!a_pre || !ul)
        continue;
    const parent = a_pre.innerHTML;
    for (const child_pre of ul.querySelectorAll('.pre'))
        if (child_pre.innerHTML.startsWith(parent + '.'))
            child_pre.innerHTML = child_pre.innerHTML.substring(parent.length)
}


for (const pre of document.querySelectorAll('.pre')) {
    pre.innerHTML = pre.innerHTML.replace(/\./g, '.<wbr>')
}

for (const p of document.querySelectorAll('p')) {
    if (p.innerHTML.startsWith('Initialize self.  See help'))
        p.innerHTML = '';
}
