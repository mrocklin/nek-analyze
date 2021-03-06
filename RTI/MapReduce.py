
def get_fname(name, proc, frame, params):
  from math import log10
  from os.path import dirname, basename
  data_path = dirname(name)
  data_tag  = basename(name) 
  dir_width = int(log10(max(abs(params["io_files"])-1,1)))+1
  if params["io_files"] > 0:
    fname = "{:s}{:0{width}d}.f{:05d}".format(name, proc, frame, width=dir_width)
  else:
    fname = "{:s}/A{:0{width}d}/{:s}{:0{width}d}.f{:05d}".format(data_path, proc, data_tag, proc, frame, width=dir_width)
  return fname


def MR_init(args, params, frame):
  """ Initialize MapReduce data """
  import numpy as np
  from RTI.Grid import Grid

  params['extent'] = list(np.array(params['extent_mesh']) - np.array(params['root_mesh']))
  params['ninterp'] = int(args.ninterp*params['order'])
  if args.verbose:
    print("  Grid is ({:f}, {:f}, {:f}) [{:d}x{:d}x{:d}] with order {:d}".format(
            params['extent'][0], params['extent'][1], params['extent'][2], 
            params['shape_mesh'][0], params['shape_mesh'][1], params['shape_mesh'][2],
            params['order']))

  # base cases
  PeCell = 0.
  ReCell = 0.
  TAbs   = 0.
  TMax   = 0.
  TMin   = 0.
  UAbs   = 0.
  dx_max = 0.
  data   = Grid(args.ninterp * params['order'],
                params['root_mesh'],
                params['extent_mesh'],
                np.array(params['shape_mesh'], dtype=int) * int(args.ninterp * params['order']),
                boxes = args.boxes)

  # return a cleaned up version of locals
  ans = locals()
  del ans['np']
  del ans['Grid']
  del ans['args']

  from interfaces.nek.files import NekFile
  njob_per_file = max(1+int((args.thread-1) / abs(int(params["io_files"]))),1)
  jobs = []
  for j in range(abs(int(params["io_files"]))):
      fname = get_fname(args.name, j, frame, params)
      input_file = NekFile(fname)
      ans["time"] = input_file.time
      elm_per_thread = int((input_file.nelm-1) / njob_per_file) + 1
      for i in range(njob_per_file):
          jobs.append([
              (i * elm_per_thread, min((i+1)*elm_per_thread, input_file.nelm)),
              fname,
              params,
              args,
              ans])  
      input_file.close()
  return jobs


def map_(input_file, pos, nelm_to_read, params, scratch = None):
  """ Map operations onto chunk of elements """
  import numpy as np
  from utils.my_utils import lagrange_matrix
  from utils.my_utils import transform_field_elements
  from utils.my_utils import transform_position_elements
  from tictoc import tic, toc
  from interfaces.nek.mesh import UniformMesh

  ans = {}
  if scratch != None:
    ans = scratch

  mesh = UniformMesh(input_file, params)
  mesh.load(pos, nelm_to_read)
  nelm, pos, vel, p, t = input_file.get_elem(nelm_to_read, pos)

  # Let's compute the x, y, and z 1D bases
  cart_x = np.linspace(0., params['extent'][0], num=params['ninterp'],endpoint=False)/params['shape_mesh'][0]
  gll_x  = pos[0:params['order'],0,0] - pos[0,0,0]

  cart_y = np.linspace(0., params['extent'][1], num=params['ninterp'],endpoint=False)/params['shape_mesh'][1]
  gll_y  = pos[0:params['order']*params['order']:params['order'],1,0] - pos[0,1,0]

  cart_z = np.linspace(0., params['extent'][2], num=params['ninterp'],endpoint=False)/params['shape_mesh'][2]
  gll_z  = pos[0:params['order']**3:params['order']**2,2,0] - pos[0,2,0]

  # and then just use y
  cart = cart_y; gll = gll_y
  trans = lagrange_matrix(gll, cart)

  # pos[0,:,:] is invariant under transform, and it is all we need
  pos_trans = pos[0,:,:]
  #pos_trans = np.transpose(pos[0,:,:])

  # transform all the fields at once
  hunk = np.concatenate((p, t, vel[:,0,:], vel[:,1,:], vel[:,2,:]), axis=1)
  hunk_trans = transform_field_elements(hunk, trans, cart)
  p_trans, t_trans, ux_trans, uy_trans, uz_trans = np.split(hunk_trans, 5, axis=1)

  # Save some results pre-renorm
  max_speed = np.sqrt(mesh.max(
                np.square(mesh.fld('u')) 
              + np.square(mesh.fld('v')) 
              + np.square(mesh.fld('w'))
                              ))
  ans['TMax']   = float(mesh.max(mesh.fld('t')))
  ans['TMin']   = float(mesh.min(mesh.fld('t')))
  ans['UAbs']   = float( max_speed)
  ans['dx_max'] = float(np.max(gll[1:] - gll[0:-1]))

  # Renorm t -> [0,1]
  tic()
  Tt_low = -params['atwood']/2.; Tt_high = params['atwood']/2.
  t_trans = (t_trans - Tt_low)/(Tt_high - Tt_low)
  #t_trans = np.maximum(t_trans, -1.)
  #t_trans = np.minimum(t_trans, 2.)
  toc('renorm')

  # stream the elements into the grid structure
  ans['data'].add(pos_trans, p_trans, t_trans, ux_trans, uy_trans, uz_trans)

def reduce_(whole, part):
  """ Reduce results into a single output object (dict) """
  whole['TMax']   = float(max(whole['TMax'],   part['TMax']))
  whole['TMin']   = float(min(whole['TMin'],   part['TMin']))
  whole['UAbs']   = float(max(whole['UAbs'],   part['UAbs']))
  whole['dx_max'] = float(max(whole['dx_max'], part['dx_max']))

  if 'data' in whole:
    whole['data'].merge(part['data'])
  else:
    whole['data'] = part['data']

  return 

