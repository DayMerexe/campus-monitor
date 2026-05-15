const pptxgen = require('pptxgenjs');
const html2pptx = require('C:/Users/DayMer/.claude/skills/davila7-claude-code-templates-pptx/scripts/html2pptx.js');

async function main() {
    const pptx = new pptxgen();
    pptx.layout = 'LAYOUT_16x9';
    pptx.author = '答辩人';
    pptx.title = '应急场景下的校园人流量监测预警系统 - 中期答辩';

    const slidesDir = 'F:/bishe/ppt-slides';

    // Slide 1: Cover
    await html2pptx(`${slidesDir}/slide1.html`, pptx);

    // Slide 2: TOC
    await html2pptx(`${slidesDir}/slide2.html`, pptx);

    // Slide 3: Background
    await html2pptx(`${slidesDir}/slide3.html`, pptx);

    // Slide 4: Architecture
    await html2pptx(`${slidesDir}/slide4.html`, pptx);

    // Slide 5: Hardware
    await html2pptx(`${slidesDir}/slide5.html`, pptx);

    // Slide 6: Software
    await html2pptx(`${slidesDir}/slide6.html`, pptx);

    // Slide 7: YOLOv8
    await html2pptx(`${slidesDir}/slide7.html`, pptx);

    // Slide 8: Key Tech
    await html2pptx(`${slidesDir}/slide8.html`, pptx);

    // Slide 9: Test Results (with performance table)
    const { slide: slide9, placeholders } = await html2pptx(`${slidesDir}/slide9.html`, pptx);

    if (placeholders.length > 0) {
        const perfData = [
            [
                { text: "指标", options: { fill: { color: "1a56db" }, color: "FFFFFF", bold: true, fontSize: 12 } },
                { text: "数值", options: { fill: { color: "1a56db" }, color: "FFFFFF", bold: true, fontSize: 12 } }
            ],
            ["检测帧率", "10-15 FPS (CPU 推理)"],
            ["报警响应延迟", "< 1 秒 (3 帧确认)"],
            ["STM32 控制响应", "< 100ms"],
            ["Web 页面刷新", "2 秒"]
        ];

        slide9.addTable(perfData, {
            x: placeholders[0].x,
            y: placeholders[0].y,
            w: placeholders[0].w,
            h: placeholders[0].h,
            colW: [placeholders[0].w * 0.4, placeholders[0].w * 0.6],
            border: { pt: 1, color: "333355" },
            align: "center",
            valign: "middle",
            fontSize: 12,
            color: "E0E6ED",
            fill: { color: "252536" }
        });
    }

    // Slide 10: Summary
    await html2pptx(`${slidesDir}/slide10.html`, pptx);

    // Slide 11: Thanks
    await html2pptx(`${slidesDir}/slide11.html`, pptx);

    const outPath = 'F:/bishe/中期答辩.pptx';
    await pptx.writeFile({ fileName: outPath });
    console.log('PPTX saved to: ' + outPath);
}

main().catch(e => { console.error(e); process.exit(1); });
