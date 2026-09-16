# Note for John: NIFoS board post attachment 2-2

This is not a letter to send anywhere. It is a short instruction for John,
because it needs a human with a browser and physical judgment, not an agent
action.

**What to do:** open this URL in a browser:

https://nifos.forest.go.kr/kfsweb/cop/bbs/selectBoardArticle.do?nttId=3207026&bbsId=BBSMSTR_1036&mn=UKFR_03_03_01&orgId=kfri

Find the attachment labeled "2-2" (첨부 2-2, or similarly numbered among the
post's attachments) and download it. Save it into `research/lit/sources/`
using a descriptive filename that keeps the original title recognizable
(for example `nifos_<post-title-slug>_attachment_2-2.<ext>`), rather than a
generic name like `attachment.pdf`.

**Why an agent cannot do this:** this board page is a NIFoS (국립산림과학원)
내부 게시판 style page. Session-bound downloads, captchas or login-gated
attachments are exactly the case this program's failure policy asks agents
to stop on rather than loop around, and browsing a Korean government board
UI and picking the right attachment among several by eye is a task suited to
a human, not worth building fragile scraping for one file.

**After it is saved:** note the file's sha256, byte size and the access date
in `research/data/REGISTRY.yaml` if it becomes a dataset input, or in
`research/lit/`'s own bibliography if it is a citation source (A1 does not
own `research/lit/`, so leave that update to whichever agent owns it, or to
John).
