#include "ndsaturate.h"

/*  A test saturation algorithm for natural deduction calculus
 * 
 * 
 * 
 * 
 * 
 * 
*/

int NDSaturate(ProofState_p state, ProofControl_p control, long
                  step_limit, long proc_limit, long unproc_limit, long
                  total_limit, long generated_limit, long tb_insert_limit,
                  long answer_limit)          
{
   ND_p ndcontrol = NDAlloc(state);
   NDSet_p ndset = NDSetAlloc();
   //ND_Derivation_p derivation = NDDerivationAlloc(NULL,NULL);
   NDSetInsert(ndset,ndcontrol);
   WFormula_p selected = NULL;
   WFormula_p selected_copy = NULL;
   bool success = false;
   //int assumption_status = 0;
   
   /*  Initialize connection to Scoring Server
   */  
   
   	int socketDescriptor;
	struct sockaddr_in serverAddress;

	bzero(&serverAddress,sizeof(serverAddress));

	serverAddress.sin_family=AF_INET;
	serverAddress.sin_addr.s_addr=inet_addr("127.0.0.1");
	serverAddress.sin_port=htons(5500);

	socketDescriptor=socket(AF_INET,SOCK_STREAM,0);
	
	connect(socketDescriptor,(struct sockaddr*)&serverAddress,sizeof(serverAddress));
   
   /*  Initialize the proof state
   */
   
   FormulaSet_p axiom_archive = FormulaSetAlloc();
   
   FormulaSetCopyFormulas(ndcontrol->nd_generated,state->f_axioms);
   FormulaSetCopyFormulas(ndcontrol->nd_derivation,state->f_axioms);
   NDPInitializeDerivationGoal(ndcontrol,ndcontrol->nd_generated);
   FormulaSetUpdateControlSymbols(ndcontrol,ndcontrol->nd_generated);
   
   FormulaSetCopyFormulas(axiom_archive,ndcontrol->nd_generated);
   
   srand(time(0));
   printf("\n%ld\n",ndcontrol->nd_generated->members);
   int counter = 0;
   int success_state = 0;
   
   /*  Begin Proof Search
   */
   
   restart:
   
   while (success == false)
   {
	  counter++;
	  
	  int start_new_assumption = rand()%100;  // 1/100 chance of starting new assumption...
	  
	  if (start_new_assumption == 0)
	  {
		  // assumption status is 0 if assumption attempt is abandoned
		  // 1 if contradiction found
		  // 2 if goal was reached by lhs of sequent assumption
		  printf("\nstart new assumption\n");
		  int assumption_status = 0;
		  assumption_status = NDStartNewAssumption(ndcontrol,socketDescriptor);
		  //assumptioncounter++;
		  printf("\nexit assumption\n");
		  if (assumption_status == 0)
		  {
			  printf("\nno assumption success\n");
		  }
		  else if (assumption_status == 1)
		  {
			  printf("\nproof by contradiction\n");
			  success = true;
		  }
		  else if (assumption_status == 2)
		  {
			  printf("\nreached goal in assumption\n");
			  success = true;
		  }
		  else
		  {
			  printf("assumption return invalid\n");
		  }
	  }
	  
	  
	  /*  Go through a socket to get the highest score from the scoring server
	   *  Message sent is the string representation of the formula in ND generated, message received is the corresponding score.  
	   *  Choose highest score...
	  */ 
	  selected = NDSelectHighestScoreRandomly(ndcontrol->nd_generated);
	  //selected = NDSelectHighestScoreThroughSocket(ndcontrol->nd_generated,socketDescriptor);
	  /*
	  */
	  selected_copy = WFormulaFlatCopy(selected);
	  FormulaSetInsert(ndcontrol->nd_derivation,selected_copy);
	  //printf("\ngenerated formulas in main loop: %ld\n",ndcontrol->nd_generated->members);
	  printf("\n");
	  WFormulaPrint(GlobalOut,selected,true);
	  //printf("\n___generating___\n");
	  NDGenerateAndScoreFormulas(ndcontrol,selected);
	  if (NDFormulaSetCheckForContradictions(ndcontrol,ndcontrol->nd_derivation))
	  {
		  //printf("\nfound contradiction\n");
		  success_state = 1;
		  success = true;
	  }
	  //printf("\nchecking for goal reach\n");
	  if ((ndcontrol->goal) && NDPDerivationGoalIsReached(ndcontrol))
	  {
		  //printf("\nreached goal\n");
		  success_state = 2;
		  success = true;
	  }
	  if (ndcontrol->nd_derivation->members > 200)
	  {
		  printf("\nmax derivation length\n");
		  NDResetState(ndcontrol);
		  FormulaSetCopyFormulas(ndcontrol->nd_generated,axiom_archive);
		  FormulaSetCopyFormulas(ndcontrol->nd_derivation,state->f_axioms);
		  goto restart;
	  }
   }
   
   printf("\n Here is the derivation the loop succeeded in finding:\n");
   FormulaSetPrint(GlobalOut,ndcontrol->nd_derivation,true);
   switch (success_state)
   {
	   case 0:
	      printf("\nfailure\n");
	      NDFree(ndcontrol);
	      FormulaSetFree(axiom_archive);
	      return 0;
	      
	   case 1: 
	      printf("\ncontradiction\n");
	      NDFree(ndcontrol);
	      FormulaSetFree(axiom_archive);
	      return 1;
	   case 2:
	      printf("\nreached goal\n");
	      NDFree(ndcontrol);
	      FormulaSetFree(axiom_archive);
	      return 2;
   }
   NDSetFree(ndset);
   FormulaSetFree(axiom_archive);
   //FormulaSetFree(ndcontrol->nd_generated);
   //FormulaSetFree(ndcontrol->nd_temporary_formulas);
   return 0;
}

int NDStartNewAssumption(ND_p ndcontrol, int socketDescriptor)
{
	TFormula_p assumption = NULL;
	WFormula_p assumption_formula = NULL;
	bool success = false;
	WFormula_p selected = NULL;
	WFormula_p selected_copy = NULL;
	ND_p assumption_control = NDAllocAssumption(ndcontrol);
	int return_state = 0;
	
	// select the assumption
	// possible assumptions: negation of parent's goal 
	// if goal is an implication can choose left hand side of implication
	// otherwise, can assume an instantiation of an existentially quantified formula, goal is parents goal
	
	if (ndcontrol->goal)  // if we are searching for contradiction there is no goal
	{
		assumption_control->goal = ndcontrol->goal;
		assumption = TFormulaFCodeAlloc(assumption_control->terms,
										assumption_control->terms->sig->not_code,
										assumption_control->goal->tformula,
										NULL);
		assumption_formula = WTFormulaAlloc(assumption_control->terms,assumption);
		
		
		printf("\nassumption_formula:\n");
		WFormulaPrint(GlobalOut,assumption_formula,true);
		
		FormulaSetInsert(assumption_control->nd_derivation,assumption_formula);
		assumption_control->last_assumption = assumption_formula;
	}
	
	//Allocate the derivation for this branch, ensures that parent has access to it when the branch is closed
	/*
	if(ndcontrol->last_assumption_branch)
	{
		NDDerivationFree(ndcontrol->last_assumption_branch);
	}
	ND_Derivation_p branch = NDDerivationAlloc(assumption_control->goal,assumption_formula);
	ndcontrol->last_assumption_branch = branch;
	*/
	
	//add the previous steps to our assumption branch
	FormulaSetCopyFormulas(assumption_control->nd_generated,ndcontrol->nd_derivation);
	
	//check to see that we have something to select from
	if (assumption_control->nd_generated->members == 0)
	{
		printf("\nno generated formulas in assumption, surfacing\n");
		return_state = 0;
		success = true; // skip the while loop and give up the assumtion: no axioms??
	}
	printf("\nentering assumption dive\n");
	// for now the only possible assumption is the negation of the parent's goal, done above
	while (success == false)
	{
		if (assumption_control->nd_generated->members == 0)
		{
			printf("\nout of generated formulas\n");
			return_state = 0;
			break;
		}
		// engage in new derivation beginning with assumption of first step
		// reuse much from the main loop
		/*
		int start_new_assumption = rand()%6;  // 1/6 chance of starting new assumption
	    
		if (start_new_assumption == 0)
		{
			// assumption status is 0 if assumption attempt is abandoned
			// 1 if contradiction found
			// 2 if goal was reached by lhs of sequent assumption
			printf("start new assumption\n");
			int assumption_status = 0;
			assumption_status = NDStartNewAssumption(ndcontrol,socketDescriptor);
			//printf("\nexit assumption\n");
			if (assumption_status == 0)
			{
				printf("no assumption success\n");
			}
			if (assumption_status == 1)
			{
				printf("\nproof by contradiction\n");
				success = true;
			}
			if (assumption_status == 2)
			{
				printf("\nreached goal in assumption\n");
				success = true;
			}
		}
		*/
		//selected = NULL;
		selected = NDSelectHighestScoreRandomly(assumption_control->nd_generated);
		if (!selected)
		{
			printf("NULL selected in assumption");
			break;
		}
		//selected = NDSelectHighestScoreThroughSocket(ndcontrol->nd_generated,socketDescriptor);
		//selected_copy = WFormulaFlatCopy(selected);
		//FormulaSetInsert(branch->nd_derivation,selected_copy);
		FormulaSetExtractEntry(selected);
		FormulaSetInsert(assumption_control->nd_derivation,selected);
		printf("\n");
		WFormulaPrint(GlobalOut,selected,true);
		NDGenerateAndScoreFormulasSkeleton(assumption_control,selected);
		
		if (NDFormulaSetCheckForContradictions(assumption_control,assumption_control->nd_derivation))
		{
			printf("\nAssumption led to contradiction\n");
			success = true;
			return_state = 1;
		}
		if ((ndcontrol->goal) && NDPDerivationGoalIsReached(assumption_control))
		{
			printf("\nreached goal of assumption\n");
			success = true;
			return_state = 2;
		}
		if (assumption_control->nd_derivation->members > 50)
		{
			printf("\nexcess derivation size: %ld\n",assumption_control->nd_derivation->members);
			break;
		}
	}
	NDAssumptionControlFree(assumption_control);
	printf("\nsurface\n");
	//exit(0);
	// change ndcontrol appropriately
	// 1) if we obtained a contradiction, add the negation of the assumption to the parent derivation
	// 2) if we obtained the goal, set our assumption as the new goal of parent
	// free the unnecessary parts of the current derivation
	return return_state;
}
