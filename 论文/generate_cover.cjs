const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  ImageRun, AlignmentType, BorderStyle, WidthType } = require('docx');
const fs = require('fs');

const A4_W = 11906;
const A4_H = 16838;
const MARGIN = 1800; // ~1.25 inch like template

const fontHei = "SimHei";  // 黑体
const fontSong = "SimSun"; // 宋体
const fontFang = "FangSong"; // 仿宋

// Convert pt to half-points (docx unit)
function pt(h) { return Math.round(h * 2); }

function emptyPara() {
  return new Paragraph({ spacing: { before: 0, after: 0, line: 240 }, children: [] });
}

// Cover page
const coverArt = fs.readFileSync('F:\\bishe\\论文\\艺术字_校名.png');

const coverChildren = [
  emptyPara(), emptyPara(), emptyPara(), emptyPara(),
  // WordArt school name as image
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 240, line: 240 },
    children: [new ImageRun({
      type: "png",
      data: coverArt,
      transformation: { width: 415, height: 97 }, // 1026x243 scaled to ~5.35in x 1.25in
      altText: { title: "应急管理大学", description: "应急管理大学校名", name: "school_name" }
    })]
  }),
  emptyPara(), emptyPara(),
  // "本科毕业设计（论文）" — 一号黑体 = 26pt = 52 half-pt
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 480, line: 240 },
    children: [new TextRun({ text: "本科毕业设计（论文）", size: pt(26), bold: true, font: fontHei })]
  }),
  emptyPara(), emptyPara(), emptyPara(),
  // Info fields - each is a row with label + underline placeholder
  // Using a table for alignment, labels in 黑体 bold, values in 仿宋
  ...buildInfoTable(),
  emptyPara(), emptyPara(), emptyPara(), emptyPara(), emptyPara(),
  // Date
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 0 },
    children: [new TextRun({ text: "20    年    月    日", size: pt(16), font: fontFang })]
  }),
];

function buildInfoTable() {
  const fields = [
    ["姓    名", "姓    名"],
    ["学    号", "学    号"],
    ["学    院", "×××××××学院"],
    ["专    业", "×××××××专业"],
    ["指导教师", "×××"],
    ["职    称", "×××"],
  ];
  const rows = fields.map(([label, placeholder]) => {
    return new TableRow({
      height: { value: 700, rule: "atLeast" },
      children: [
        // Label cell — 黑体 bold 三号(~16pt)
        new TableCell({
          width: { size: 2600, type: WidthType.DXA },
          borders: { top: { style: BorderStyle.NONE }, bottom: { style: BorderStyle.NONE },
                     left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE } },
          verticalAlign: "center",
          margins: { top: 60, bottom: 60, left: 80, right: 80 },
          children: [new Paragraph({ alignment: AlignmentType.DISTRIBUTE, children: [
            ...label.split("").map(c => new TextRun({ text: c, size: pt(16), bold: true, font: fontHei }))
          ]})]
        }),
        // Value cell — Times New Roman 三号，模板要求
        new TableCell({
          width: { size: 3200, type: WidthType.DXA },
          borders: { top: { style: BorderStyle.NONE }, bottom: { style: BorderStyle.SINGLE, size: 1, color: "000000" },
                     left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE } },
          verticalAlign: "center",
          margins: { top: 60, bottom: 60, left: 80, right: 80 },
          children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
            new TextRun({ text: placeholder, size: pt(16), font: "Times New Roman" })
          ]})]
        }),
      ]
    });
  });
  return [new Table({
    width: { size: 5800, type: WidthType.DXA },
    columnWidths: [2600, 3200],
    alignment: AlignmentType.CENTER,
    rows
  })];
}

// Declaration page
const declChildren = [
  emptyPara(), emptyPara(),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 400 },
    children: [new TextRun({ text: "毕业设计（论文）原创性声明", size: pt(15), bold: true, font: fontHei })]
  }),
  emptyPara(), emptyPara(),
  bodyPara("本人郑重声明：所呈交的毕业设计（论文），是本人在指导教师的指导下，独立进行研究所取得的原创性成果。除文中已经注明引用的内容外，本毕业设计（论文）不包含任何其他个人或集体已经发表或撰写过的研究成果。对本文的研究做出重要贡献的个人和集体，均已在文中明确标明。"),
  emptyPara(),
  bodyPara("本人完全意识到本声明的法律后果由本人承担。"),
  emptyPara(), emptyPara(), emptyPara(), emptyPara(),
  rightSig("毕业设计（论文）作者（签名）：______________"),
  emptyPara(),
  rightSig("                    年    月    日"),
  emptyPara(), emptyPara(),
  rightSig("指导教师（签名）：______________"),
  emptyPara(),
  rightSig("                    年    月    日"),
];

// 版权使用授权书
const copyrightChildren = [
  emptyPara(), emptyPara(), emptyPara(), emptyPara(),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 200 },
    children: [new TextRun({ text: "毕业设计（论文）版权使用授权书", size: pt(15), bold: true, font: fontHei })]
  }),
  emptyPara(), emptyPara(),
  bodyPara("本人完全了解应急管理大学有权保留并向国家有关部门或机构送交毕业设计（论文）的复印件和磁盘，允许毕业设计（论文）被查阅和借阅。本人授权应急管理大学可以将毕业设计（论文）的全部或部分内容编入有关数据库进行检索，可以采用影印、缩印或其它复制手段保存、汇编毕业设计（论文）。"),
  emptyPara(), emptyPara(), emptyPara(), emptyPara(),
  rightSig("毕业设计（论文）作者（签名）：______________"),
  emptyPara(),
  rightSig("                    年    月    日"),
  emptyPara(), emptyPara(),
  rightSig("指导教师（签名）：______________"),
  emptyPara(),
  rightSig("                    年    月    日"),
];

// Helpers
function bodyPara(text) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { before: 0, after: 0, line: 360 },
    indent: { firstLine: 480 },
    children: [new TextRun({ text, size: pt(12), font: fontSong })]
  });
}

function rightSig(text) {
  return new Paragraph({
    alignment: AlignmentType.RIGHT,
    spacing: { before: 0, after: 0 },
    children: [new TextRun({ text, size: pt(12), font: fontSong })]
  });
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: fontSong, size: 24 } } },
  },
  sections: [
    {
      properties: { page: { size: { width: A4_W, height: A4_H }, margin: { top: 1200, bottom: 1200, left: MARGIN, right: MARGIN } } },
      children: coverChildren
    },
    // 扉页
    {
      properties: { page: { size: { width: A4_W, height: A4_H }, margin: { top: 2000, bottom: 1440, left: MARGIN, right: MARGIN } } },
      children: declChildren
    },
    {
      properties: { page: { size: { width: A4_W, height: A4_H }, margin: { top: 2000, bottom: 1440, left: MARGIN, right: MARGIN } } },
      children: copyrightChildren
    },
  ]
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync('F:\\bishe\\论文\\封面与声明.docx', buf);
  console.log("Done: 封面与声明.docx");
});
