"""Prepara spay_video_ok.mp4 para o preloader do portfólio."""

import argparse
from pathlib import Path
import shutil
import subprocess


RAIZ = Path(__file__).resolve().parent.parent

# Registro do enquadramento 1280x720 do vídeo fornecido na tela 1024x1024
# da logo original. O ajuste é constante: não adiciona movimento de câmera.
FILTROS = (
    'scale=1774:998:flags=lanczos,pad=1774:1024:0:16:black,'
    'crop=1024:1024:376:0,scale=768:768:flags=lanczos,'
    'format=yuv420p,setpts=PTS-STARTPTS,fps=24'
)


def main():
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument('origem', type=Path, help='Arquivo spay_video_ok.mp4 original')
    argumentos.add_argument('--ffmpeg', help='Caminho opcional do executável FFmpeg')
    argumentos.add_argument(
        '--saida', type=Path,
        default=RAIZ / 'static/videos/hv-preloader.webm',
    )
    opcoes = argumentos.parse_args()
    executavel = opcoes.ffmpeg or shutil.which('ffmpeg')
    if not executavel:
        try:
            import imageio_ffmpeg
            executavel = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            argumentos.error('Informe --ffmpeg ou instale FFmpeg no ambiente de desenvolvimento.')

    if not opcoes.origem.is_file():
        argumentos.error('O vídeo de origem não foi encontrado.')
    opcoes.saida.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        executavel, '-hide_banner', '-loglevel', 'error',
        '-i', str(opcoes.origem),
        '-vf', FILTROS, '-map', '0:v:0', '-an',
        '-c:v', 'libvpx-vp9', '-crf', '30', '-b:v', '0', '-g', '48',
        '-deadline', 'good', '-cpu-used', '2', '-row-mt', '1',
        '-pix_fmt', 'yuv420p', '-y', str(opcoes.saida),
    ], check=True)
    print(f'{opcoes.saida}: {opcoes.saida.stat().st_size:,} bytes')


if __name__ == '__main__':
    main()
