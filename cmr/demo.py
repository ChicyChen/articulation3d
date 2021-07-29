#!/usr/bin/python
"""
Demo code: given arbitrary input image of at least part of a human, predict mesh

python demo.py --checkpoint=data/models/ours/2020_02_29-18_30_01.pt --img demo/instructions_coffee_0004_00001634.jpg
"""
from __future__ import division
from __future__ import print_function

import torch
from torchvision.transforms import Normalize
import numpy as np
import cv2
import argparse
import json
import glob

from utils import Mesh
from models import CMR, SMPL
from utils.imutils import preprocess_generic
from utils.renderer_p3d import Pytorch3dRenderer
from models.geometric_layers import orthographic_projection
import config as cfg
import os
import os.path as osp

os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "0"


if torch.cuda.is_available():
    DEVICE = torch.device("cuda") 
    print("Running on the GPU")
else:
    DEVICE = torch.device("cpu")
    print("Running on the CPU")


parser = argparse.ArgumentParser()
parser.add_argument('--checkpoint', default=None, help='Path to pretrained checkpoint')
parser.add_argument('--img', type=str, required=True, help='Path to input image')

colors = {
    # colorbline/print/copy safe:
    'light_gray':  [0.9, 0.9, 0.9],
    'light_purple':  [0.8, 0.53, 0.53],
    'light_green': [166/255.0, 178/255.0, 30/255.0],
    'light_blue': [0.65098039, 0.74117647, 0.85882353],
}

def __get_input_type(args):
    input_type =None
    image_exts = ('jpg', 'png', 'jpeg', 'bmp')
    video_exts = ('mp4', 'avi', 'mov')
    extension = osp.splitext(args.img)[1][1:]

    if extension.lower() in video_exts:
        input_type ='video'
    elif extension.lower() in image_exts:
        input_type = 'image'
        print(extension.lower())
    elif osp.isdir(args.img):
        file_list = os.listdir(args.img)
        assert len(file_list) >0, f"{args.img} is a blank folder"
        extension = osp.splitext(file_list[0])[1][1:]
        assert extension.lower() in image_exts
        input_type ='image_dir'
    else:
        assert False, "Unknown input path. It should be an image, or an image folder, or a video file"
    return input_type




def setup_input(args):
    """
    Input type can be 
        an image file
        a video file
        a folder with image files
    """
    image_exts = ('jpg', 'png', 'jpeg', 'bmp')
    video_exts = ('mp4', 'avi', 'mov')

    # get type of input 
    input_type = __get_input_type(args)

    if input_type =='video':
        cap = cv2.VideoCapture(args.img)
        assert cap.isOpened(), f"Failed in opening video: {args.img}"
        # __video_setup(args)
        return input_type, cap

    elif input_type =='image':
        return input_type, args.img

    elif input_type =='image_dir':
        image_list = gnu.get_all_files(args.img, image_exts, "relative") 
        image_list = [ osp.join(args.img, image_name) for image_name in image_list ]
        # __img_seq_setup(args)
        return input_type, image_list

    else:
        assert False, "Unknown input type"


def process_image(img_file, input_res=224):
    """
    Read image, do preprocessing
    """
    normalize_img = Normalize(mean=cfg.IMG_NORM_MEAN, std=cfg.IMG_NORM_STD)
    #rgb_img_in = cv2.imread(img_file)[:,:,::-1].copy().astype(np.float32)
    rgb_img_in = img_file[:,:,::-1].copy().astype(np.float32)
    rgb_img = preprocess_generic(rgb_img_in, input_res)
    disp_img = preprocess_generic(rgb_img_in, input_res, display=True)
    img = np.transpose(rgb_img.astype('float32'),(2,0,1))/255.0
    disp_img = np.transpose(disp_img.astype('float32'),(2,0,1))/255.0
    img = torch.from_numpy(img).float()
    disp_img = torch.from_numpy(disp_img).float()
    norm_img = normalize_img(img.clone())[None]

    return disp_img, norm_img

def disp_imgs(args, pred_vertices_smpl, mesh, camera_translation, img, current_frame):
    # Render parametric shape
    # img_smpl = renderer.render(pred_vertices_smpl, mesh.faces.cpu().numpy(),
    #                            camera_t=camera_translation,
    #                            img=img, use_bg=True, body_color='pink')
    # img_smpl2 = renderer.render(pred_vertices_smpl, mesh.faces.cpu().numpy(),
    #                            camera_t=camera_translation,
    #                            img=img, use_bg=False, bg_color=(1.0, 1.0, 1.0),
    #                            body_color='pink')

    img_smpl = renderer.render(pred_vertices_smpl, mesh.faces.cpu().numpy(), img, True)
    img_smpl2 = renderer.render(pred_vertices_smpl, mesh.faces.cpu().numpy(), img, False)

    # import matplotlib
    # matplotlib.use('agg')
    # import matplotlib.pyplot as plt
    # plt.figure(1)
    # plt.clf()
    # plt.subplot(131)
    # plt.imshow(img)
    # #plt.imshow((img * 255).astype(np.uint8))
    # plt.title('input')
    # plt.axis('off')
    # plt.subplot(132)
    # plt.imshow(img_smpl)
    # #plt.imshow((img_smpl * 255).astype(np.uint8))
    # plt.title('3D Mesh overlay')
    # plt.axis('off')
    # plt.subplot(133)
    # plt.imshow(img_smpl2)
    # #plt.imshow((img_smpl2 * 255).astype(np.uint8))
    # plt.title('3D mesh')
    # plt.axis('off')
    # plt.draw()
    # plt.show()


    img_smpl = renderer.render(pred_vertices_smpl, mesh.faces.cpu().numpy(), img, True)
    img_smpl2 = renderer.render(pred_vertices_smpl, mesh.faces.cpu().numpy(), img, False)

    im_name = args.img[:-4]+'_output/frame'+str(current_frame)+'_preds'+'.png'
    combined_img = (np.concatenate((img_smpl, img_smpl2), axis=1)*255).astype(np.uint8)
    combined_img = cv2.cvtColor(combined_img, cv2.COLOR_RGB2BGR)
    cv2.imwrite(im_name, combined_img)
    print("Image saved as", im_name)
    # im_result = cv2.imread(im_name)
    # return im_result
    return combined_img

    # im_name = args.img[:-4]+'_output/frame'+str(current_frame)+'_preds'+'.png'
    # plt.savefig(im_name)
    # print("Image saved as", im_name)
    # im_result = cv2.imread(im_name)
    # return im_result


def gen_video_out(img, the_fps, img_array):
    outVideo_fileName = img[:-4]+'_output/combined_video.mp4'
    print(f">> Generating video in {outVideo_fileName}")
    
    oneim = img_array[0]
    height, width, layers = oneim.shape
    size = (width,height)
    
    
    out = cv2.VideoWriter(outVideo_fileName,cv2.VideoWriter_fourcc(*'mp4v'), the_fps, size)
    
    for i in range(len(img_array)):
        out.write(img_array[i])
    out.release()


if __name__ == '__main__':
    args = parser.parse_args()

    if not os.path.isdir(args.img[:-4]+'_output'):
        os.mkdir(args.img[:-4]+'_output')
    
    # Load model
    mesh = Mesh(device=DEVICE)
    # Our pretrained networks have 5 residual blocks with 256 channels. 
    # You might want to change this if you use a different architecture.
    model = CMR(mesh, 5, 256, pretrained_checkpoint=args.checkpoint)
    smpl = SMPL()

    model = model.to(DEVICE)
    model.eval()
    smpl = smpl.to(DEVICE)


    input_type, input_data = setup_input(args)
    img_array = []

    cur_frame = 0
    #while cur_frame < 3:
    while True:
        if input_type == 'image':
            img_original_bgr  = cv2.imread(input_data)

        elif input_type =='image_dir':
            if cur_frame < len(input_data):
                image_path = input_data[cur_frame]
                img_original_bgr  = cv2.imread(image_path)
            else:
                img_original_bgr = None

        elif input_type == 'video':      
            _, img_original_bgr = input_data.read()
        
        else:
            assert False, "Unknown input_type"

        cur_frame += 1
        if img_original_bgr is None:
            break

        # Preprocess input image and generate predictions
        img, norm_img = process_image(img_original_bgr, input_res=cfg.INPUT_RES)
        norm_img = norm_img.to(DEVICE)

        with torch.no_grad():
            pred_vertices, pred_vertices_smpl, pred_camera, pred_pose, pred_shape = model(norm_img)
            pred_keypoints_3d_smpl = smpl.get_joints(pred_vertices_smpl)
            pred_keypoints_2d_smpl = orthographic_projection(pred_keypoints_3d_smpl, pred_camera.detach())[:, :, :2].cpu().data.numpy()
            """
            #############################################################################
            #pred_vertices: Regressed non-parametric shape: size = (1, 6890, 3)
            #pred_vertices_smpl: Regressed SMPL shape: size = (1, 6890, 3)
            #############################################################################
            Below are the parameters that might be helpful to the other articulation 
            system: where camera contains the 3D space information of positions &
            the others contain the pose & shape informations
            #############################################################################
            pred_camera: Weak-perspective camera: size = (1, 3)
            pred_pose: SMPL pose parameters (as rotation matrices): size = (1, 24, 3, 3)
            pred_shape: SMPL shape parameters: size = (1, 10)
            pred_keypoints_3d_smpl, 3D joints: size = (1, 38, 3)
            pred_keypoints_2d_smpl, 2D joints: size = (1, 38, 2)
            #############################################################################
            """
        # Calculate camera parameters for rendering
        #camera_translation = torch.stack([pred_camera[:,1], pred_camera[:,2], 2*cfg.FOCAL_LENGTH/(cfg.INPUT_RES * pred_camera[:,0] +1e-9)],dim=-1)
        camera_translation = torch.stack([-pred_camera[:,1], -pred_camera[:,2], 2*cfg.FOCAL_LENGTH/(cfg.INPUT_RES * pred_camera[:,0] +1e-9)],dim=-1)
        camera_translation = camera_translation[0].cpu().numpy()
        pred_vertices = pred_vertices[0].cpu().numpy()
        pred_vertices_smpl = pred_vertices_smpl[0].cpu().numpy()
        img = img.permute(1,2,0).cpu().numpy()

        # Setup renderer for visualization
        renderer = Pytorch3dRenderer(
                    img_size=img.shape[0], 
                    mesh_color=colors['light_purple'],camera_t=camera_translation,device=DEVICE)
        
        im_result = disp_imgs(args, pred_vertices_smpl, mesh, camera_translation, img, cur_frame)
        img_array.append(im_result)

        if cur_frame == 1 and input_type == 'image':
            break
    
    if input_type == 'video':
        gen_video_out(args.img, input_data.get(cv2.CAP_PROP_FPS), img_array)

