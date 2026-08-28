
#set page(width: 6in, height: 9in)
#set heading(numbering: "1.")
#show heading.where(level: 1): it => {
  pagebreak(weak: true)
  v(30%)
  text(style: "italic", size: 10pt)[#smallcaps[Chapter #counter(heading).display()]]
  v(0.5em)
  text(size: 28pt, weight: "bold")[#it.body]
}
#heading(level: 1)[Chap 1]
Hello
#heading(level: 2)[Subhead 2]
Hello 2
#heading(level: 3)[Subhead 3]
Hello 3
#heading(level: 1)[Chap 2]
Hello 4

