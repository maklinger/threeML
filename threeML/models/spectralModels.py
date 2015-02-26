import numpy
import collections
from Parameter import Parameter
import fancyDisplay
from IPython.display import display, Latex, HTML
import math
import scipy.integrate
import operator
import numexpr
import abc

keVtoErg                 = 1.60217657E-9


class ModelValidate(object):

    def __init__(self,model):

        self.checks = ["'self.functionName' not set in *setup* ",\
                    "'self.formula' not set in *setup*",\
                    "'self.parameters' not set in *setup*",\
                    "'self.integral(e1,e2)' not defined in *setup*"\
                    ]
        checks2 = "'self.parameters' is NOT of type collections.OrderedDict"

        self.tt = [hasattr(model,'functionName'),\
                   hasattr(model,'formula'),\
                   hasattr(model,'parameters'),\
                   hasattr(model,'integral')]


        if self.tt[2]: #Check that parameters exist
            
            self.checks.append(checks2)
            self.tt.append(isinstance(model.parameters,collections.OrderedDict))

        else:

            self._printSetupErr()
            return

        if self.tt[4]: #Check that the parameters are right type

            for p in model.parameters.keys():

                self.checks.append("self.parameters[%s] is not an instance Parameter"%p)
                self.tt.append(isinstance(model.parameters[p],Parameter))
                
        self._printSetupErr()



    
    def _printSetupErr(self):

        self.tt = ~numpy.array(self.tt)
        
        self.checks =numpy.array(self.checks)

        
        problems = self.checks[self.tt]

        if len(problems) == 0:
            return

        print "Error: The SpectralModel class is not proper!"
        print "The following problems were found:"
        print
        for prob in problems:
                print "\t"+prob

        raise RuntimeError("Correct the SpectralModel definition!")        
          
        



class SpectralModel(object):
    __metaclass__           = abc.ABCMeta # Make the user code certain
    

    def __init__(self):

        import collections        
        self.setup()


        self._validate() # Raise runtime error if the users

        for k,v in self.parameters.iteritems():

            object.__setattr__(self,k,v)



        
    @abc.abstractmethod
    def setup(self):
        # virtual member implemented by the user
        pass
    
    def _validate(self):
        '''
        Member called to check that the model has all the proper
        attributes after the setup is called in the __init__ member
        '''
    
        val = ModelValidate(self)
    
    def __getattr__(self, item):
     
        
        
        if self.__dict__.has_key("parameters"):
            if self.parameters.has_key(item):
                return self.parameters[item]
            else:
                object.__getattribute__(self,item)
        else:
            object.__getattribute__(self,item)
        
    def __setattr__(self,item,value):

                
        
        if self.__dict__.has_key("parameters"):
            
            if self.parameters.has_key(item):
                (self.parameters[item]).setValue(value)
            else:
                object.__setattr__(self,item,value)
                
        else:
            
            object.__setattr__(self,item,value)

    # Removed by J. Michael to switch to a different scheme
    #def __getitem__(self,argument):
    #    return self.parameters[argument]

    def __repr__(self):
        print("Spectral model: %s" %(self.functionName))
        print("Formula:\n")
        display(Latex(self.formula))
        print("")
        print("Current parameters:\n")
        table                    = fancyDisplay.HtmlTable(8)
        table.addHeadings("Name","Value","Minimum","Maximum","Delta","Status","Unit","Prior")
        for k,v in self.parameters.iteritems():
            if(v.isFree()):
                ff                   = "free"
            else:
                ff                   = "fixed"
        
        table.addRow(v.name,v.value,v.minValue,v.maxValue,v.delta,ff,v.unit,v.prior.getName())
        
        display(HTML(table.__repr__()))
    
        return ''
 
  
    @abc.abstractmethod
    def __call__(self):
        raise NotImplemented("The method __call__ has not been implemented. This is a bug")
  
    #If there is an analytical solution to the integral of the function,
    #override these methods: the analytical way is always A LOT faster
    #than numerical integration
    def photonFlux(self,e1,e2):
        return scipy.integrate.quad(self.__call__,e1,e2,epsabs=0.01,epsrel=1e-4)[0]
   
  
    def energyFlux(self,e1,e2):
        def eF(e):
            return e*self.__call__(e)
    
        return scipy.integrate.quad(eF,e1,e2,epsabs=0,epsrel=1e-3)[0]*keVtoErg
 
  
    #The following methods define the aritmetical operations on model, so
    #that the user can define "composite" models
    def __add__(self,b):
        return CompositeModel(self,b,operator.add)
  
    def __radd__(self,b):
        return CompositeModel(self,b,operator.add)
  
    def __sub__(self,b):
        return CompositeModel(self,b,operator.sub)
  
    def __rsub__(self,b):
        return CompositeModel(self,b,operator.sub)
  
    def __div__(self,b):
        return CompositeModel(self,b,operator.div)

    def __rdiv__(self,b):
        return CompositeModel(self,b,operator.div)
  
    def __mul__(self,b):
        return CompositeModel(self,b,operator.mul)

    def __rmul__(self,b):
        return CompositeModel(self,b,operator.mul)
  


#I may have to look at how composite model is screwed up by my new scheme!!


#The following class represent the combination of two
#models with an aritmetical operation. For example,
#CompositeModel(model1,model2,operator.add) will return
#a class which will act like a (model1+model2) model.

class CompositeModel(SpectralModel):
  def __init__(self,one,two,thisOperator):
    if type(one) in (int,float):
      self.oneCall            = lambda x:float(one)
    elif issubclass(type(one),(SpectralModel,CompositeModel)):
      self.oneCall            = one.__call__
    else:
      raise NotImplementedError("Cannot execute operation with operand of type %s" %(type(one)))
    
    if type(two) in (int,float):
      self.twoCall            = lambda x:float(two)
    elif issubclass(type(two),(SpectralModel,CompositeModel)):
      self.twoCall            = two.__call__
    else:
      raise NotImplementedError("Cannot execute operation with operand of type %s" %(type(one)))
    
    self.operator             = thisOperator
    
    #Now create a parameters dictionary pointing to the
    #parameters in one and two
    self.parameters           = collections.OrderedDict()
    
    for component in [one,two]:
      if type(component) in (int,float):
        continue
      for k in component.parameters.keys():
        if(k in self.parameters.keys()):
          tokens                = k.split("_")
          if(len(tokens)==1):
            newKey              = k+"_1"
            tokens              = newKey.split("_")
          pass
          oldNum              = int(tokens[1])
          for i in range(oldNum,1000):
            newKey            = tokens[0]+"_%s" %(i)
            if(newKey not in self.parameters.keys()):
              break
            pass
          pass
        else:
          newKey                = k
        pass
        
        self.parameters[newKey] = component.parameters[k]
      pass
    pass
        
    self.formula              = "(print the components by themselves to know their formulae)"
    
    operatorNames             = {operator.add: ' + ', operator.div: ' / ', operator.mul: ' * ', operator.sub: ' - '}
    
    names                     = []
    for component in [one,two]:
      if type(component) in (int,float):
        names.insert(0,"%s" %(component))
      else:
        names.append(component.functionName)
    pass
    
    self.functionName       = "( " + operatorNames[self.operator].join(names) + " )"
    
    integrals               = []
    for component in [one,two]:
      if type(component) in (int,float):
        integrals.append(lambda e1,e2: float(component))
      else:
        integrals.append(component.integral)
      pass
    pass
    self.integral           = lambda e1,e2: integrals[0](e1,e2)+integrals[1](e1,e2)
  pass
  
  def __call__(self,x):
    return self.operator(self.oneCall(x),self.twoCall(x))
  pass
pass



