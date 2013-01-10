import code, argparse, readline, rlcompleter, sys, os, imp, inspect, logging

def parseArgs():
	parser = argparse.ArgumentParser(description="Test Client", add_help=False)
	parser.add_argument('--help', action='help')
	parser.add_argument("--file", "-f", help="a file to execute")
	parser.add_argument('--log', type=lambda l: getattr(logging, l.upper()), default=logging.INFO, help='the logging level')
	parser.add_argument("arguments", nargs="*", help="python code to execute directly")
	options = parser.parse_args()
	return options

def run(obj):
	options = parseArgs()
	logging.basicConfig(level=options.log, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
	locals = getLocals(obj)
	if options.arguments:
		runSource(locals, "\n".join(options.arguments))
	elif options.file:
		runFile(locals, options.file, options)
	else:
		runInteractive(locals)

def runInteractive(locals):
	readline.parse_and_bind("tab: complete")
	readline.set_completer(rlcompleter.Completer(locals).complete)
	console = code.InteractiveConsole(locals)
	console.interact('Type "help()" or "help(method)" for more information.')
	
def runSource(locals, source):
	interpreter = code.InteractiveInterpreter(locals)
	interpreter.runsource(source)

def runFile(locals, file, options):
	sys.path.insert(0, os.path.dirname(file))
	def shell():
		runInteractive(locals)
	locals["shell"] = shell
	__builtins__.__dict__.update(locals)
	locals["__name__"]="__main__"
	locals["__file__"]=file
	execfile(file, locals)
	sys.path.pop(0)

def getLocals(obj):
	locals = {}
	def _help(method=None):
		if method is None:
			print "Available methods:\tType help(method) for more infos."
			print ", ".join(locals.keys())
		else:
			if not isinstance(method, str):
				method = filter(lambda name: locals[name] is method, locals)[0]
			if not method:
				return "Unknown method: %s" % method
			func = locals.get(method)
			argspec = inspect.getargspec(func)
			if argspec.args:
				argstr = inspect.formatargspec(argspec.args, defaults=argspec.defaults)
			else:
				argstr = "()"
			print "Signature: " + method + argstr
			doc = func.__doc__
			if not doc:
				print "No documentation for: %s" % method
	def _load(file, name=None):
		files = filter(lambda dir: os.path.exists(os.path.join(dir, file)), sys.path)
		if files:
			file = os.path.join(files[0], file)
		if not name:
			name = os.path.basename(file)
		mod = imp.load_source(name, file)
		locals[name] = mod
		return mod
	locals.update(help=_help, load=_load)
	for func in dir(obj):
		if not func.startswith("_") and callable(getattr(obj, func)):
			locals[func] = getattr(obj, func)
	return locals
