import code, argparse, readline, rlcompleter, sys, os, imp, inspect, logging

def parseArgs():
	parser = argparse.ArgumentParser(description="Test Client", add_help=False)
	parser.add_argument('--help', action='help')
	parser.add_argument("--file", "-f", help="a file to execute")
	parser.add_argument('--log', type=lambda l: getattr(logging, l.upper()), default=logging.INFO, help='the logging level')
	parser.add_argument("arguments", nargs="*", help="python code to execute directly")
	options = parser.parse_args()
	return options

def run(obj, allowSelf=True):
	options = parseArgs()
	logging.basicConfig(level=options.log, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
	locals_ = getLocals(obj, allowSelf)
	if options.arguments:
		runSource(locals_, "\n".join(options.arguments))
	elif options.file:
		runFile(locals_, options.file, options)
	else:
		runInteractive(locals_)

def runInteractive(locals_): #@ReservedAssignment
	readline.parse_and_bind("tab: complete")
	readline.set_completer(rlcompleter.Completer(locals_).complete)
	console = code.InteractiveConsole(locals_)
	console.interact('Type "help()" or "help(method)" for more information.')
	
def runSource(locals_, source):
	interpreter = code.InteractiveInterpreter(locals_)
	interpreter.runsource(source)

def runFile(locals_, file_, options):
	sys.path.insert(0, os.path.dirname(file_))
	def shell():
		runInteractive(locals_)
	locals_["shell"] = shell
	__builtins__.__dict__.update(locals_)
	locals_["__name__"]="__main__"
	locals_["__file__"]=file_
	execfile(file_, locals_)
	sys.path.pop(0)

def getLocals(obj, allowSelf=True):
	locals_ = {}
	def _help(method=None):
		if method is None:
			print "Available methods:\tType help(method) for more infos."
			print ", ".join(locals_.keys())
		else:
			if not isinstance(method, str):
				method = filter(lambda name: locals_[name] is method, locals_)[0]
			if not method:
				return "Unknown method: %s" % method
			func = locals_.get(method)
			argspec = inspect.getargspec(func)
			if argspec.args:
				argstr = inspect.formatargspec(argspec.args, defaults=argspec.defaults)
			else:
				argstr = "()"
			print "Signature: " + method + argstr
			doc = func.__doc__
			if not doc:
				print "No documentation for: %s" % method
	def _load(file_, name=None):
		files = filter(lambda dir_: os.path.exists(os.path.join(dir_, file_)), sys.path)
		if files:
			file_ = os.path.join(files[0], file_)
		if not name:
			name = os.path.basename(file_)
		mod = imp.load_source(name, file_)
		locals_[name] = mod
		return mod
	locals_.update(help=_help, load=_load)
	for func in dir(obj):
		if not func.startswith("_"):
			locals_[func] = getattr(obj, func)
	if allowSelf:
		locals_["self"] = obj
	return locals_
