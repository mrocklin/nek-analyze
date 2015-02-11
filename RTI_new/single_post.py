"""
Post-processing module: to be completed by user
"""

def post_series(results, params, args):
  """Post-process time-series results, outputting to screen or files.

  Keyword arguments:
  results -- dictionary of ouputs of process_work keyed by time
  params  -- dictionary of problem parameters read from {name}.json
  args    -- namespace of commandline arguments from ArgumentParser
  """

  import numpy as np
  import matplotlib
  if not args.display:
    matplotlib.use('Agg')
  import matplotlib.pyplot as plt

  # Post-post processing
  if args.series: 
    results_with_times = sorted([[float(elm[0]), elm[1]] for elm in results.items()])
    times, vals = zip(*results_with_times)
    times = np.array(times, dtype=np.float64)
 
    # Numerical stability plot
    from utils.my_utils import find_root
    PeCs  = np.array([d['PeCell'] for d in vals])
    TMaxs = np.array([d['TAbs']   for d in vals])
    for i in range(1,TMaxs.shape[0]):
      if TMaxs[i] > TMaxs[0]:
        print("Simulation went unstable at t={:f}, PeCell={:f}+/-{:f}".format(times[i], (PeCs[i]+PeCs[i-1])/2, (PeCs[i]-PeCs[i-1])/2))
        break
 
    plt.figure()
    ax1 = plt.subplot(1,1,1)
    plt.xlabel('Time (s)')
    ax1.plot(times, np.log(PeCs),          label='Log[Cell Peclet]')
    ax1.plot(times, TMaxs*2./params['atwood'], 'gx', label='max(T)/max(T0)')
    plt.ylim(ymin = 0)
    plt.legend(loc=2)
    plt.savefig("{:s}-stability.png".format(args.name))

    """ 
    # Make a bunch of movies
    from os import devnull
    from subprocess import call
    foo = open(devnull, 'w')
    codec = "ffvhuff"
    if args.slice:
      call("rm -f "+args.name+"-zslice.mkv", shell=True)
      call("avconv -f image2 -i {:s}%05d-zslice.png -c:v {:s} {:s}-zslice.mkv".format(args.name, codec, args.name), shell=True, stdout = foo, stderr = foo)
      call("rm -f "+args.name+"-yslice.mkv", shell=True)
      call("avconv -f image2 -i {:s}%05d-yslice.png -c:v {:s} {:s}-yslice.mkv".format(args.name, codec, args.name), shell=True, stdout = foo, stderr = foo)
    if args.mixing_cdf:
      call("rm -f "+args.name+"-cdf.mkv", shell=True)
      call("avconv -f image2 -i {:s}%05d-cdf.png -c:v {:s} {:s}-cdf.mkv".format(args.name, codec, args.name), shell=True, stdout = foo, stderr = foo)
    if args.Fourier:
      call("rm -f "+args.name+"-spectrum.mkv", shell=True)
      call("avconv -f image2 -i {:s}%05d-spectrum.png -c:v {:s} {:s}-spectrum.mkv".format(args.name, codec, args.name), shell=True, stdout = foo, stderr = foo) 
    if args.mixing_zone: 
      call("rm -f "+args.name+"-prof.mkv", shell=True)
      call("avconv -f image2 -i {:s}%05d-prof.png -c:v {:s} {:s}-prof.mkv".format(args.name, codec, args.name), shell=True, stdout = foo, stderr = foo) 
    foo.close()
    """
 
    # mixing zone analysis
    from utils.my_utils import compute_alpha, compute_reynolds, compute_Fr

    hs_visual = [d['h_visual'] for d in vals]
    Fr_visual = compute_Fr(hs_visual, times) / np.sqrt(params['atwood']*params['g']*params['extent_mesh'][0])
    alpha_visual = np.array(compute_alpha(hs_visual, times)) / (params['atwood']*params['g'])

    plt.figure()
    ax1 = plt.subplot(1,2,1)
    plt.xlabel('Time (s)')
    plt.ylabel('h (m)')
    plt.ylim([0., params['extent_mesh'][2]])
    ax1.plot(times, hs_visual)

    ax2 = plt.subplot(1,2,2)
    plt.xlabel('Time (s)')
    plt.ylabel('Fr (m)')
    plt.ylim([0., 1.5])
    ax2.plot(times, Fr_visual)
    #Fr_analytic = np.sqrt(1./3.14159265358)
    Fr_analytic = np.sqrt(
                    2*params['atwood']*params['g']/(1+params['atwood']) / (2*np.pi*params['kmin']) + (2.*np.pi*params['kmin'] * params['viscosity'])**2
                         ) - (2.*np.pi*params['kmin'] * (params['viscosity'] + params['conductivity']))
    Fr_analytic /= np.sqrt(params['atwood'] * params['g'] / params['kmin'] / (1+ params['atwood']))
    ax2.plot([0., times[-1]], [Fr_analytic]*2)
    
    plt.savefig("{:s}-h.png".format(args.name))

    plt.figure()
    Xs = [d['Xi'] for d in vals]
    Ts = [d['Theta'] for d in vals]
    ax1 = plt.subplot(1,2,1)
    plt.ylim([0.,1.])
    ax1.plot(times, Xs)
    ax1.plot(times, Ts)
    plt.xlabel('Time (s)')
    plt.ylabel('$\Xi, \Theta$')

    Re_visual = np.array(compute_reynolds(hs_visual, times)) / (params['viscosity'])
    ax2 = plt.subplot(1,2,2)
    ax2.plot(times, Re_visual)
    plt.xlabel('Time (s)')
    plt.ylabel('Re')

    plt.savefig("{:s}-Xi.png".format(args.name))

    plt.figure()
    Ps = np.array([d['P'] for d in vals])
    Ks = np.array([d['K'] for d in vals])
    ax1 = plt.subplot(1,1,1)
    hs_cabot = [d['h_cabot'] for d in vals]
    budget = (params['atwood'] * params['g'] * np.square(hs_cabot) * 
             (params["extent_mesh"][0] - params["root_mesh"][0]) *
             (params["extent_mesh"][1] - params["root_mesh"][1]) / 2.)
    ax1.plot(times, np.divide(Ps-Ps[0], budget), label='Potential')
    ax1.plot(times, np.divide(Ks      , budget), label='Kinetic')
    plt.xlabel('Time (s)')
    plt.ylabel('Energy / h^2')
    plt.legend(loc=2)
    plt.savefig("{:s}-energy.png".format(args.name))

  if args.display:
    plt.show()
    
  return


def post_frame(ans, args, params, frame):
  import matplotlib
  matplotlib.use('Agg')

  # Analysis! 
  ans['TAbs'] = max(ans['TMax'], -ans['TMin'])
  ans['PeCell'] = ans['UAbs']*ans['dx_max']/params['conductivity']
  ans['ReCell'] = ans['UAbs']*ans['dx_max']/params['viscosity']
  if args.verbose:
    print("  Extremal temperatures {:f}, {:f}".format(ans['TMax'], ans['TMin']))
    print("  Max speed: {:f}".format(ans['UAbs']))
    print("  Cell Pe: {:f}, Cell Re: {:f}".format(ans['PeCell'], ans['ReCell']))

  return 
