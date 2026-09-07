"""Convert the actual browser recording to a shareable MP4 with burned captions."""
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.tools'))
import imageio_ffmpeg


def main():
    out = ROOT / 'deliverables'
    cues = [
        (0,10,'知微在工作台右侧汇总当前诉求、已知事实、待核实与下一步。'),
        (10,18,'筛选高关注会话；搜索会话 ID，快速定位原始对话。'),
        (18,30,'逐条推进历史回放，只分析当前时点已经出现的信息。'),
        (30,38,'归档快照单独展示事后工单；重要判断可回到原话。'),
        (38,47,'无回执的退款与到账承诺会先降级为核实表达。'),
        (47,55,'安全回复仍由客服编辑；模拟发送只发生在本机。'),
        (55,65,'确认跟进任务并保存到本地，保留人工决定权。'),
        (65,71,'评估区分官方开发集与独立人工 Challenge Set。'),
        (71,75,'Qwen 缺钥时明确降级；现场是否联网如实显示。')
    ]
    def stamp(seconds):
        return f'{seconds//3600:02d}:{seconds//60%60:02d}:{seconds%60:02d},000'
    caption='\n\n'.join(f'{i+1}\n{stamp(a)} --> {stamp(b)}\n{t}' for i,(a,b,t) in enumerate(cues))+'\n'
    (out/'demo-subtitles.srt').write_text(caption,encoding='utf-8')
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    filters="pad=iw:ih+80:0:0:color=0x163d38,subtitles=demo-subtitles.srt:force_style='FontName=Noto Sans SC,FontSize=14,PrimaryColour=&H00FFFFFF,Outline=0,Shadow=0,MarginV=8'"
    subprocess.run([ffmpeg,'-y','-i','demo.webm','-vf',filters,'-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart','知微_实际操作演示.mp4'],cwd=out,check=True)
    subprocess.run([ffmpeg,'-y','-ss','3','-i','知微_实际操作演示.mp4','-frames:v','1','video-preview.png'],cwd=out,check=True)


if __name__=='__main__':
    main()
