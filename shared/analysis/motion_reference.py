"""Show the SAME RGB565 texture stationary and moving, without game/shaders.

The only transform is an integer circular translation. The window is movable
between monitors; no display settings are read or changed. --check is headless.
"""
import argparse
import time

import numpy as np
from PIL import Image


def load_image(path,frame):
    with np.load(path) as archive:
        a = archive['frames'][frame].astype(np.uint32)
    rgb = np.stack(((a>>11)*255//31,((a>>5)&63)*255//63,(a&31)*255//31),axis=2).astype(np.uint8)
    return rgb


def translated(rgb,step,rate):
    # 160 horizontal and 80 vertical game pixels/second: same speed in both
    # modes. 40 -> (4,2) per step, 80 -> (2,1). No interpolation or colour edits.
    return np.roll(rgb,((80//rate)*step,(160//rate)*step),axis=(0,1))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('capture')
    ap.add_argument('--frame',type=int,default=100)
    ap.add_argument('--check',action='store_true')
    args = ap.parse_args()
    rgb = load_image(args.capture,args.frame)
    if args.check:
        moving = translated(rgb,17,40)
        assert np.array_equal(np.sort(moving.reshape(-1,3),axis=0),np.sort(rgb.reshape(-1,3),axis=0))
        assert np.array_equal(translated(rgb,17,40),translated(rgb,34,80))
        print('PASS: RGB histogram unchanged; 40/80 modes have identical displacement at equal elapsed time; no window opened.')
        return
    import tkinter as tk
    from PIL import ImageTk
    # Keep photo pixels at native size when the window crosses monitors with
    # different Windows scaling. This affects only this diagnostic process.
    import ctypes
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError,OSError):
        ctypes.windll.user32.SetProcessDPIAware()
    root = tk.Tk()
    root.title('Проверка движения — перетащи окно между MSI и ASUS')
    root.configure(bg='#dddddd')
    root.resizable(False,False)
    tk.Label(root,text='Слева неподвижно, справа движется та же текстура. Яркость программно не меняется.',
             bg='#dddddd',font=('Segoe UI',11)).grid(row=0,column=0,columnspan=2,padx=16,pady=12)
    for col,title in enumerate(('Неподвижная текстура','Движущаяся текстура')):
        tk.Label(root,text=title,bg='#dddddd',font=('Segoe UI',10)).grid(row=1,column=col,pady=(0,6))
    h,w = rgb.shape[:2]
    photo = ImageTk.PhotoImage(Image.fromarray(rgb))
    left = tk.Label(root,image=photo,borderwidth=0)
    left.grid(row=2,column=0,padx=(16,8))
    right = tk.Label(root,image=photo,borderwidth=0)
    right.grid(row=2,column=1,padx=(8,16))
    state = dict(rate=40,start=time.perf_counter(),step=-1,photo=photo)
    status = tk.StringVar(value='40 кадров/с. Перетащи окно на другой монитор и сравни.')
    def choose(rate):
        state.update(rate=rate,start=time.perf_counter(),step=-1)
        status.set(('40 кадров/с' if rate==40 else '80 кадров/с') if rate else 'Остановлено')
        if not rate:
            state['photo'] = photo
            right.configure(image=photo)
    controls = tk.Frame(root,bg='#dddddd')
    controls.grid(row=3,column=0,columnspan=2,pady=12)
    for label,rate in [('40 кадров/с',40),('80 кадров/с',80),('Остановить',0)]:
        tk.Button(controls,text=label,width=17,command=lambda r=rate:choose(r)).pack(side='left',padx=5)
    tk.Label(root,textvariable=status,bg='#dddddd',font=('Segoe UI',10)).grid(row=4,column=0,columnspan=2,pady=(0,8))
    tk.Label(root,text='Этот тест не запускает игру и не меняет настройки монитора.\n'
                       'Заметь: темнеет ли правая область только во время движения?',
             bg='#dddddd',font=('Segoe UI',10)).grid(row=5,column=0,columnspan=2,pady=(0,12))
    def tick():
        rate = state['rate']
        if rate:
            step = int((time.perf_counter()-state['start'])*rate)
            if step!=state['step']:
                state['step'] = step
                state['photo'] = ImageTk.PhotoImage(Image.fromarray(translated(rgb,step,rate)))
                right.configure(image=state['photo'])
        root.after(4,tick)
    tick()
    root.mainloop()


if __name__=='__main__':
    main()
